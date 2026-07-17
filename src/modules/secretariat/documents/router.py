from fastapi import APIRouter, Depends, Request, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from src.core.security import get_current_user, require_secretary, require_admin_or_secretary
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount

from . import schemas, service, repository

documents_router = APIRouter(prefix="/secretariat", tags=["Secretariat — Document Requests"])


@documents_router.post(
    "/documents/request",
    response_model=schemas.DocumentRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_document_request(
    request: Request,
    data: schemas.DocumentRequestCreate,
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.submit_document_request(
        db=db,
        requestor_id=current_user.account_id,
        data=data,
        ip_address=request.client.host if request.client else None,
    )


@documents_router.post(
    "/documents/external",
    response_model=schemas.DocumentRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_external_document_request(
    request: Request,
    data: schemas.ExternalDocumentRequestCreate,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_secretary),
):
    return service.submit_external_document_request(
        db=db,
        secretary_id=_sec.account_id,
        secretary_email=_sec.email_address,
        data=data,
        ip_address=request.client.host if request.client else None,
    )


@documents_router.get("/documents/my", response_model=List[schemas.DocumentRequestResponse])
def get_my_document_requests(
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return repository.fetch_document_requests(db, requestor_account_id=current_user.account_id)


@documents_router.get("/documents/track/{reference_number}", response_model=schemas.DocumentTrackResponse)
def track_document_request(
    reference_number: str,
    db: Session = Depends(get_database_session),
):
    return service.track_document_request(db, reference_number)


@documents_router.get("/documents", response_model=List[schemas.DocumentRequestResponse])
def list_document_requests(
    status_filter: str = Query(default="ALL"),
    requestor_type: str = Query(default=None),
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(require_admin_or_secretary),
):
    resolved_status = None if status_filter == "ALL" else status_filter
    return repository.fetch_document_requests(db, status_filter=resolved_status, requestor_type=requestor_type)


@documents_router.get("/documents/{request_id}", response_model=schemas.DocumentRequestResponse)
def get_document_request(
    request_id: int,
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(require_admin_or_secretary),
):
    req = repository.fetch_document_request_by_id(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Document request not found.")
    return req


@documents_router.patch("/documents/{request_id}/advance", response_model=schemas.DocumentRequestResponse)
def advance_document_request(
    request_id: int,
    request: Request,
    data: schemas.DocumentStatusAdvance,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_admin_or_secretary),
):
    return service.advance_document_request_status(
        db=db,
        request_id=request_id,
        data=data,
        secretary_id=_sec.account_id,
        secretary_email=_sec.email_address,
        ip_address=request.client.host if request.client else None,
    )
