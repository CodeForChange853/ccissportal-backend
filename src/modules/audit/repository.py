# backend-v2/src/modules/audit/repository.py

from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
from datetime import datetime, timezone
from . import models


def create_event(
    database_session: Session,
    event_type:    str,
    actor_id:      Optional[int]  = None,
    actor_email:   Optional[str]  = None,
    target_type:   Optional[str]  = None,
    target_id:     Optional[str]  = None,
    ip_address:    Optional[str]  = None,
    payload:       Optional[dict] = None,
    anomaly_score: float          = 0.0,
    narrative_status: str         = 'NONE',
) -> models.AuditEvent:
    event = models.AuditEvent(
        actor_id=actor_id,
        actor_email=actor_email,
        event_type=event_type,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        ip_address=ip_address,
        payload=payload,
        anomaly_score=anomaly_score,
        narrative_status=narrative_status,
    )
    database_session.add(event)
    database_session.commit()
    database_session.refresh(event)
    return event


def fetch_events(
    database_session: Session,
    event_type:  Optional[str] = None,
    actor_email: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[models.AuditEvent]:
    query = database_session.query(models.AuditEvent)
    if event_type:
        query = query.filter(models.AuditEvent.event_type == event_type)
    if actor_email:
        query = query.filter(models.AuditEvent.actor_email.ilike(f"%{actor_email}%"))
    return query.order_by(desc(models.AuditEvent.created_at)).offset(skip).limit(limit).all()


def fetch_high_anomalies(
    database_session: Session,
    threshold: float = 70.0,
    limit: int = 10,
) -> list[models.AuditEvent]:
    return (
        database_session.query(models.AuditEvent)
        .filter(models.AuditEvent.anomaly_score >= threshold)
        .order_by(desc(models.AuditEvent.anomaly_score))
        .limit(limit)
        .all()
    )


def count_events(database_session: Session) -> int:
    return database_session.query(models.AuditEvent).count()


# SE-08 helpers

def fetch_pending_narrative_events(
    database_session: Session,
    limit: int = 5,
) -> list[models.AuditEvent]:
    return (
        database_session.query(models.AuditEvent)
        .filter(models.AuditEvent.narrative_status == 'PENDING')
        .order_by(desc(models.AuditEvent.anomaly_score))
        .limit(limit)
        .all()
    )


def fetch_event_by_id(database_session: Session, event_id: int) -> Optional[models.AuditEvent]:
    return database_session.query(models.AuditEvent).filter(models.AuditEvent.event_id == event_id).first()


def set_narrative_status(
    database_session: Session,
    event: models.AuditEvent,
    status: str,
) -> models.AuditEvent:
    event.narrative_status = status
    database_session.commit()
    database_session.refresh(event)
    return event


def save_narrative(
    database_session: Session,
    event: models.AuditEvent,
    narrative: str,
) -> models.AuditEvent:
    event.anomaly_narrative = narrative
    event.narrative_status  = 'GENERATED'
    database_session.commit()
    database_session.refresh(event)
    return event


def acknowledge_narrative(
    database_session: Session,
    event: models.AuditEvent,
) -> models.AuditEvent:
    event.narrative_acknowledged_at = datetime.now(timezone.utc)
    database_session.commit()
    database_session.refresh(event)
    return event