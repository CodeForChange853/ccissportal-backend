from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import models, schemas, repository
from src.modules.audit import service as audit_service


def create_mapping_draft(
    db: Session,
    data: schemas.SubjectMappingDraftCreate,
    secretary_id: int,
    secretary_email: str,
    ip_address: Optional[str] = None,
) -> models.SubjectMappingDraft:
    from src.modules.auth.models import UserAccount
    student = db.query(UserAccount).filter(UserAccount.account_id == data.student_account_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student account not found.")

    draft = models.SubjectMappingDraft(
        student_account_id=data.student_account_id,
        prepared_by_secretary_id=secretary_id,
        previous_institution=data.previous_institution,
        previous_program=data.previous_program,
        mapping_entries=[e.model_dump() for e in data.mapping_entries],
        status="DRAFT",
    )
    saved = repository.save_mapping_draft(db, draft)

    audit_service.log_event(
        database_session=db,
        event_type="MAPPING_DRAFT_CREATED",
        actor_id=secretary_id,
        actor_email=secretary_email,
        target_type="subject_mapping_draft",
        target_id=saved.id,
        ip_address=ip_address,
        payload={
            "student_id":           data.student_account_id,
            "previous_institution": data.previous_institution,
            "entries_count":        len(data.mapping_entries),
        },
    )
    return saved


def update_mapping_draft(
    db: Session,
    draft_id: int,
    data: schemas.SubjectMappingDraftUpdate,
    secretary_id: int,
) -> models.SubjectMappingDraft:
    draft = repository.fetch_mapping_draft_by_id(db, draft_id)
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping draft not found.")
    if draft.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only DRAFT mappings can be edited (current status: {draft.status}).",
        )
    if draft.prepared_by_secretary_id != secretary_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the secretary who created this draft.",
        )

    if data.previous_institution is not None:
        draft.previous_institution = data.previous_institution
    if data.previous_program is not None:
        draft.previous_program = data.previous_program
    if data.mapping_entries is not None:
        draft.mapping_entries = [e.model_dump() for e in data.mapping_entries]

    db.commit()
    db.refresh(draft)
    return draft


def submit_mapping_for_approval(
    db: Session,
    draft_id: int,
    secretary_id: int,
    secretary_email: str,
    ip_address: Optional[str] = None,
) -> models.SubjectMappingDraft:
    draft = repository.fetch_mapping_draft_by_id(db, draft_id)
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping draft not found.")
    if draft.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only DRAFT mappings can be submitted (current status: {draft.status}).",
        )
    if not draft.mapping_entries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit an empty mapping — add at least one subject entry first.",
        )

    draft.status = "SUBMITTED_FOR_APPROVAL"
    db.commit()
    db.refresh(draft)

    audit_service.log_event(
        database_session=db,
        event_type="MAPPING_SUBMITTED_FOR_APPROVAL",
        actor_id=secretary_id,
        actor_email=secretary_email,
        target_type="subject_mapping_draft",
        target_id=draft_id,
        ip_address=ip_address,
        payload={"student_id": draft.student_account_id},
    )
    return draft


def decide_mapping_draft(
    db: Session,
    draft_id: int,
    decision_data: schemas.MappingApprovalDecision,
    admin_id: int,
    admin_email: str,
    ip_address: Optional[str] = None,
) -> schemas.MappingApprovalResult:
    if decision_data.decision not in ("APPROVED", "REJECTED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be APPROVED or REJECTED.",
        )

    draft = repository.fetch_mapping_draft_by_id(db, draft_id)
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping draft not found.")
    if draft.status != "SUBMITTED_FOR_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only SUBMITTED_FOR_APPROVAL mappings can be decided (current: {draft.status}).",
        )

    now = datetime.now(timezone.utc)
    subjects_credited = 0

    if decision_data.decision == "APPROVED":
        draft.status               = "APPROVED"
        draft.approved_by_admin_id = admin_id
        draft.approved_at          = now
        draft.admin_notes          = decision_data.admin_notes

        from src.modules.faculty.models import GradebookEntry
        for entry in (draft.mapping_entries or []):
            if entry.get("recommended_action") != "CREDIT":
                continue
            ccis_id = entry.get("ccis_subject_id")
            if not ccis_id:
                continue
            credited = GradebookEntry(
                student_account_id=draft.student_account_id,
                curriculum_subject_id=ccis_id,
                faculty_account_id=admin_id,
                final_grade=1.0,
                completion_status="PASSED",
                override_reason=(
                    f"Subject credited via transferee/shifter evaluation — "
                    f"{entry.get('previous_subject_code', '')}: "
                    f"{entry.get('previous_subject_name', '')}"
                ),
            )
            db.add(credited)
            subjects_credited += 1

        message = f"Mapping approved. {subjects_credited} subject(s) credited to the student's gradebook."
    else:
        draft.status               = "REJECTED"
        draft.rejected_by_admin_id = admin_id
        draft.rejected_at          = now
        draft.admin_notes          = decision_data.admin_notes
        message = "Mapping rejected."

    db.commit()

    audit_service.log_event(
        database_session=db,
        event_type="MAPPING_DECISION_MADE",
        actor_id=admin_id,
        actor_email=admin_email,
        target_type="subject_mapping_draft",
        target_id=draft_id,
        ip_address=ip_address,
        payload={
            "decision":          decision_data.decision,
            "student_id":        draft.student_account_id,
            "subjects_credited": subjects_credited,
        },
    )

    return schemas.MappingApprovalResult(
        mapping_id=draft_id,
        status=draft.status,
        subjects_credited=subjects_credited,
        message=message,
    )
