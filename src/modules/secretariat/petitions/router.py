from fastapi import APIRouter, Depends, Request, Query, status
from sqlalchemy.orm import Session
from typing import List

from src.core.security import get_current_user, require_secretary, require_admin_or_secretary
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount

from . import schemas, service, repository

petition_router = APIRouter(prefix="/secretariat", tags=["Secretariat — Subject Petitions"])


@petition_router.post("/petitions", response_model=schemas.SubjectPetitionResponse, status_code=status.HTTP_201_CREATED)
def submit_petition(
    request: Request,
    data: schemas.SubjectPetitionCreate,
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.submit_petition(
        db=db,
        student_id=current_user.account_id,
        data=data,
        ip_address=request.client.host if request.client else None,
    )


@petition_router.get("/petitions/my", response_model=List[schemas.SubjectPetitionResponse])
def get_my_petitions(
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return repository.fetch_petitions(db, student_id=current_user.account_id)


@petition_router.get("/petitions", response_model=List[schemas.SubjectPetitionResponse])
def list_petitions(
    status_filter: str = Query(default="ALL"),
    petition_type: str = Query(default=None),
    student_id: int = Query(default=None),
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(require_admin_or_secretary),
):
    resolved_status = None if status_filter == "ALL" else status_filter
    return repository.fetch_petitions(
        db,
        status_filter=resolved_status,
        student_id=student_id,
        petition_type=petition_type,
    )


@petition_router.get("/petitions/{petition_id}", response_model=schemas.SubjectPetitionResponse)
def get_petition(
    petition_id: int,
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(get_current_user),
):
    return service.get_petition_by_id(db, petition_id)


@petition_router.patch("/petitions/{petition_id}/secretary-action", response_model=schemas.SubjectPetitionResponse)
def secretary_act_on_petition(
    petition_id: int,
    request: Request,
    data: schemas.SecretaryPetitionAction,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_secretary),
):
    return service.act_on_petition_as_secretary(
        db=db,
        petition_id=petition_id,
        data=data,
        secretary_id=_sec.account_id,
        secretary_email=_sec.email_address,
        ip_address=request.client.host if request.client else None,
    )


@petition_router.patch("/petitions/{petition_id}/admin-decision", response_model=schemas.SubjectPetitionResponse)
def admin_decide_petition(
    petition_id: int,
    request: Request,
    data: schemas.AdminPetitionDecision,
    db: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin_or_secretary),
):
    return service.act_on_petition_as_admin(
        db=db,
        petition_id=petition_id,
        data=data,
        admin_id=_admin.account_id,
        admin_email=_admin.email_address,
        ip_address=request.client.host if request.client else None,
    )
