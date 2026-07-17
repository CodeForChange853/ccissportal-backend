from fastapi import APIRouter, Depends, Request, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from src.core.security import require_secretary, require_admin_or_secretary
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount

from . import schemas, service, repository

mapping_router = APIRouter(prefix="/secretariat", tags=["Secretariat — Subject Mapping"])


@mapping_router.post(
    "/mapping/draft",
    response_model=schemas.SubjectMappingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_mapping_draft(
    request: Request,
    data: schemas.SubjectMappingDraftCreate,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_secretary),
):
    return service.create_mapping_draft(
        db=db,
        data=data,
        secretary_id=_sec.account_id,
        secretary_email=_sec.email_address,
        ip_address=request.client.host if request.client else None,
    )


@mapping_router.get("/mapping", response_model=List[schemas.SubjectMappingResponse])
def list_mapping_drafts(
    status_filter: str = Query(default="ALL"),
    student_id: int = Query(default=None),
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(require_admin_or_secretary),
):
    resolved = None if status_filter == "ALL" else status_filter
    return repository.fetch_all_mapping_drafts(db, status_filter=resolved, student_id=student_id)


@mapping_router.get("/mapping/student/{student_id}", response_model=List[schemas.SubjectMappingResponse])
def list_student_mappings(
    student_id: int,
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(require_admin_or_secretary),
):
    return repository.fetch_all_mapping_drafts(db, student_id=student_id)


@mapping_router.get("/mapping/{draft_id}", response_model=schemas.SubjectMappingResponse)
def get_mapping_draft(
    draft_id: int,
    db: Session = Depends(get_database_session),
    _viewer: UserAccount = Depends(require_admin_or_secretary),
):
    draft = repository.fetch_mapping_draft_by_id(db, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Mapping draft not found.")
    return draft


@mapping_router.patch("/mapping/{draft_id}", response_model=schemas.SubjectMappingResponse)
def update_mapping_draft(
    draft_id: int,
    data: schemas.SubjectMappingDraftUpdate,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_secretary),
):
    return service.update_mapping_draft(db=db, draft_id=draft_id, data=data, secretary_id=_sec.account_id)


@mapping_router.patch("/mapping/{draft_id}/submit", response_model=schemas.SubjectMappingResponse)
def submit_mapping_for_approval(
    draft_id: int,
    request: Request,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_secretary),
):
    return service.submit_mapping_for_approval(
        db=db,
        draft_id=draft_id,
        secretary_id=_sec.account_id,
        secretary_email=_sec.email_address,
        ip_address=request.client.host if request.client else None,
    )


@mapping_router.patch("/mapping/{draft_id}/decide", response_model=schemas.MappingApprovalResult)
def decide_mapping_draft(
    draft_id: int,
    request: Request,
    data: schemas.MappingApprovalDecision,
    db: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin_or_secretary),
):
    return service.decide_mapping_draft(
        db=db,
        draft_id=draft_id,
        decision_data=data,
        admin_id=_admin.account_id,
        admin_email=_admin.email_address,
        ip_address=request.client.host if request.client else None,
    )


@mapping_router.delete("/mapping/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mapping_draft(
    draft_id: int,
    db: Session = Depends(get_database_session),
    _sec: UserAccount = Depends(require_secretary),
):
    draft = repository.fetch_mapping_draft_by_id(db, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Mapping draft not found.")
    if draft.status != "DRAFT":
        raise HTTPException(
            status_code=400,
            detail=f"Only DRAFT mappings can be deleted (current status: {draft.status}).",
        )
    repository.delete_mapping_draft(db, draft)
