# backend-v2/src/modules/audit/service.py

from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone

from . import repository, schemas, models

# ── Anomaly score cache — avoids refitting IsolationForest on every request ──
import time as _time
_score_cache: dict = {"score": 0.0, "ts": 0.0}
_SCORE_TTL_SECONDS = 300  

def _score(events: list[models.AuditEvent]) -> float:

    global _score_cache

    now = _time.monotonic()
    if now - _score_cache["ts"] < _SCORE_TTL_SECONDS:
        return _score_cache["score"]

    if len(events) < 5:
        return 0.0

    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest

        SENSITIVE = {
            'GRADE_MODIFIED', 'SETTING_CHANGED', 'PASSKEY_ROTATED',
            'USER_SUSPENDED', 'ENROLLMENT_REJECTED',
        }

        actor_counts: dict[str, int] = {}
        for e in events:
            key = e.actor_email or 'anon'
            actor_counts[key] = actor_counts.get(key, 0) + 1

        X = []
        for e in events:
            hour       = e.created_at.hour if e.created_at else 12
            is_sens    = int(e.event_type in SENSITIVE)
            actor_freq = actor_counts.get(e.actor_email or 'anon', 1)
            X.append([hour, is_sens, actor_freq])

        clf   = IsolationForest(contamination=0.1, random_state=42)
        preds = clf.fit_predict(np.array(X))
        score = round(min((preds == -1).mean() * 200, 100.0), 1)

        _score_cache = {"score": score, "ts": now}
        return score
    except Exception:
        return 0.0


SENSITIVE_TYPES = {
    'GRADE_MODIFIED', 'SETTING_CHANGED', 'PASSKEY_ROTATED',
    'USER_SUSPENDED', 
}


def log_event(
    database_session: Session,
    event_type:  str,
    actor_id:    Optional[int]  = None,
    actor_email: Optional[str]  = None,
    target_type: Optional[str]  = None,
    target_id:   Optional[str]  = None,
    ip_address:  Optional[str]  = None,
    payload:     Optional[dict] = None,
) -> models.AuditEvent:

    # 1. Calculate the Heuristic Score
    hour = datetime.now(timezone.utc).hour
    off_hours = hour < 7 or hour > 22
    is_sensitive = event_type in SENSITIVE_TYPES

    heuristic_score = 0.0
    if off_hours and is_sensitive:
        heuristic_score = 75.0
    elif off_hours or is_sensitive:
        heuristic_score = 35.0

    # 2. AUTOMATED THREAT MITIGATION (The Tripwire)
    if heuristic_score >= 75.0 and actor_email:
        from src.modules.auth import repository as auth_repo
        
        # ── BUG FIX: Don't suspend the Admin if they are doing their job late at night ──
        user = auth_repo.fetch_user_by_email(database_session, actor_email)
        is_admin = user and user.account_role == "ADMIN"

        if not is_admin:
            auth_repo.lock_user_account(database_session=database_session, target_email=actor_email)
            
            if payload is None:
                payload = {}
            payload["threat_mitigation_engaged"] = True
            payload["action_taken"] = "ACCOUNT_AUTO_SUSPENDED"
        else:
            if payload is None:
                payload = {}
            payload["threat_mitigation_engaged"] = False
            payload["action_taken"] = "ADMIN_EXEMPT_FROM_TRIPWIRE"

    return repository.create_event(
        database_session=database_session,
        event_type=event_type,
        actor_id=actor_id,
        actor_email=actor_email,
        target_type=target_type,
        target_id=str(target_id) if target_id else None,
        ip_address=ip_address,
        payload=payload,
        anomaly_score=heuristic_score,
    )


def get_events(
    database_session: Session,
    event_type:  Optional[str] = None,
    actor_email: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[models.AuditEvent]:
    return repository.fetch_events(
        database_session=database_session,
        event_type=event_type,
        actor_email=actor_email,
        skip=skip,
        limit=limit,
    )


def get_summary(database_session: Session) -> schemas.AuditSummaryOut:
    recent = repository.fetch_events(database_session, limit=100)
    high   = repository.fetch_high_anomalies(database_session)
    total  = repository.count_events(database_session)
    score  = _score(recent)

    return schemas.AuditSummaryOut(
        total_events=total,
        high_anomalies=len(high),
        anomaly_score=score,
        top_anomalies=high[:5],
    )