from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import List

from src.core.security import require_admin_or_secretary
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount

from . import schemas, service

cor_router = APIRouter(prefix="/secretariat", tags=["Secretariat — COR Release"])


@cor_router.get("/cor", response_model=List[schemas.CORQueueItem])
def list_cor_queue(
    cor_status: str = Query(default="ALL", description="PENDING | RELEASED | ALL"),
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_admin_or_secretary),
):
    resolved = None if cor_status == "ALL" else cor_status
    return service.get_cor_queue(db, cor_status=resolved)


@cor_router.patch("/cor/{request_id}/release", response_model=schemas.CORQueueItem)
def release_student_cor(
    request_id: int,
    data: schemas.CORReleaseAction,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_admin_or_secretary),
):
    return service.release_cor(db=db, request_id=request_id, secretary_id=_sec.account_id)
