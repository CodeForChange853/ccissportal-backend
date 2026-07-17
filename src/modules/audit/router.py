# backend-v2/src/modules/audit/router.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from src.core.database_setup import get_database_session
from src.core.security import require_admin
from src.modules.auth.models import UserAccount
from . import service, schemas

audit_router = APIRouter(prefix="/audit", tags=["Audit Intelligence"])


@audit_router.get("/events", response_model=list[schemas.AuditEventOut])
def list_audit_events(
    event_type:  Optional[str] = Query(None),
    actor_email: Optional[str] = Query(None),
    skip:  int = Query(0,  ge=0),
    limit: int = Query(50, ge=1, le=200),
    database_session: Session  = Depends(get_database_session),
    _: UserAccount             = Depends(require_admin),
):
    return service.get_events(
        database_session=database_session,
        event_type=event_type,
        actor_email=actor_email,
        skip=skip,
        limit=limit,
    )


@audit_router.get("/summary", response_model=schemas.AuditSummaryOut)
def get_audit_summary(
    database_session: Session = Depends(get_database_session),
    _: UserAccount            = Depends(require_admin),
):
    return service.get_summary(database_session=database_session)


# SE-08 — Trigger narrative generation for PENDING events
@audit_router.post(
    "/process-narratives",
    response_model=schemas.NarrativeRunResponse,
)
def process_narratives(
    database_session: Session = Depends(get_database_session),
    _: UserAccount            = Depends(require_admin),
):
    result = service.process_pending_narratives(database_session)
    return schemas.NarrativeRunResponse(**result)


# SE-08 — Mark a narrative as acknowledged by admin
@audit_router.post(
    "/events/{event_id}/acknowledge-narrative",
    response_model=schemas.AuditEventOut,
)
def acknowledge_narrative(
    event_id: int,
    database_session: Session = Depends(get_database_session),
    _: UserAccount            = Depends(require_admin),
):
    event = service.acknowledge_narrative(database_session, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit event #{event_id} not found.",
        )
    return event