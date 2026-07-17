from fastapi import APIRouter, Depends, Request, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from src.core.security import get_current_user, require_admin_or_secretary, require_faculty
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount

from . import schemas, service, repository

completion_router = APIRouter(prefix="/secretariat", tags=["Secretariat — INC Completion"])


@completion_router.post(
    "/completion/request",
    response_model=schemas.CompletionRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_completion_request(
    request: Request,
    data: schemas.CompletionRequestCreate,
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.submit_completion_request(
        db=db,
        student_id=current_user.account_id,
        data=data,
        ip_address=request.client.host if request.client else None,
    )


@completion_router.get("/completion/my-requests", response_model=List[schemas.CompletionRequestResponse])
def get_my_completion_requests(
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return repository.fetch_completion_requests(db, student_id=current_user.account_id)


@completion_router.get("/completion/queue", response_model=List[schemas.CompletionRequestResponse])
def get_completion_queue(
    state_filter: str = Query(default="ALL"),
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(require_admin_or_secretary),
):
    resolved = None if state_filter == "ALL" else state_filter
    return repository.fetch_completion_requests(db, state_filter=resolved)


@completion_router.get("/completion/faculty-queue", response_model=List[schemas.CompletionRequestResponse])
def get_faculty_completion_queue(
    db: Session = Depends(get_database_session),
    _faculty: UserAccount = Depends(require_faculty),
):
    return repository.fetch_completion_requests_for_faculty(db, faculty_account_id=_faculty.account_id)


@completion_router.get("/completion/{request_id}", response_model=schemas.CompletionRequestResponse)
def get_completion_request(
    request_id: int,
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(get_current_user),
):
    req = repository.fetch_completion_request_by_id(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Completion request not found.")
    return req


@completion_router.patch("/completion/{request_id}/advance", response_model=schemas.CompletionRequestResponse)
def advance_completion_workflow(
    request_id: int,
    request: Request,
    data: schemas.CompletionWorkflowAdvance,
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.advance_completion_workflow(
        db=db,
        request_id=request_id,
        actor_id=current_user.account_id,
        actor_email=current_user.email_address,
        actor_role=current_user.account_role,
        data=data,
        ip_address=request.client.host if request.client else None,
    )
