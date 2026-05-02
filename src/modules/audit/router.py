# backend-v2/src/modules/audit/router.py

from fastapi import APIRouter, Depends, Query
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