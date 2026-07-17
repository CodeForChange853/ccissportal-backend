from fastapi import APIRouter, Depends, Request, Query, status
from sqlalchemy.orm import Session
from typing import List

from src.core.security import get_current_user, require_secretary, require_admin_or_secretary
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount

from . import schemas, service, repository

ojt_router = APIRouter(prefix="/secretariat", tags=["Secretariat — OJT Clearance"])


@ojt_router.post("/ojt/submit", response_model=schemas.OJTSubmissionResponse, status_code=status.HTTP_201_CREATED)
def submit_ojt_documents(
    request: Request,
    submission_data: schemas.OJTSubmissionCreate,
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.submit_ojt_documents(
        db=db,
        student_id=current_user.account_id,
        submission_data=submission_data,
        ip_address=request.client.host if request.client else None,
    )


@ojt_router.get("/ojt/pending", response_model=List[schemas.OJTSubmissionResponse])
def get_pending_ojt_submissions(
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_admin_or_secretary),
):
    return repository.fetch_all_ojt_submissions(db, status_filter="PENDING")


@ojt_router.get("/ojt/all", response_model=List[schemas.OJTSubmissionResponse])
def get_all_ojt_submissions(
    status_filter: str = Query(default="ALL", description="PENDING | VERIFIED | REJECTED | ALL"),
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_admin_or_secretary),
):
    resolved = None if status_filter == "ALL" else status_filter
    return repository.fetch_all_ojt_submissions(db, status_filter=resolved)


@ojt_router.patch("/ojt/{submission_id}/verify", response_model=schemas.OJTSubmissionResponse)
def verify_ojt_submission(
    submission_id: int,
    request: Request,
    verification_data: schemas.OJTVerificationUpdate,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_secretary),
):
    return service.process_ojt_verification(
        db=db,
        submission_id=submission_id,
        secretary_id=_sec.account_id,
        secretary_email=_sec.email_address,
        verification_data=verification_data,
        ip_address=request.client.host if request.client else None,
    )


@ojt_router.get("/ojt/my-status", response_model=schemas.OJTClearanceStatusResponse)
def get_my_ojt_status(
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.get_ojt_clearance_status(db=db, student_id=current_user.account_id)


@ojt_router.get("/ojt/student/{account_id}/status", response_model=schemas.OJTClearanceStatusResponse)
def get_student_ojt_status(
    account_id: int,
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(require_admin_or_secretary),
):
    return service.get_ojt_clearance_status(db=db, student_id=account_id)
