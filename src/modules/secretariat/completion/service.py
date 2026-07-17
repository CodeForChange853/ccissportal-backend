from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import models, schemas, repository
from src.modules.audit import service as audit_service

_VALID_TRANSITIONS: dict[tuple[str, str], set[str]] = {
    ("PENDING_FEE",            "ROUTED_TO_FACULTY"):      {"SECRETARY", "ADMIN"},
    ("PENDING_FEE",            "REJECTED"):               {"SECRETARY", "ADMIN"},
    ("ROUTED_TO_FACULTY",      "AWAITING_ADMIN_POSTING"): {"FACULTY"},
    ("AWAITING_ADMIN_POSTING", "POSTED"):                 {"ADMIN"},
    ("AWAITING_ADMIN_POSTING", "REJECTED"):               {"ADMIN"},
}


def submit_completion_request(
    db: Session,
    student_id: int,
    data: schemas.CompletionRequestCreate,
    ip_address: Optional[str] = None,
) -> models.CompletionRequest:
    from src.modules.faculty.models import GradebookEntry

    entry = db.query(GradebookEntry).filter(
        GradebookEntry.grade_id == data.gradebook_entry_id,
        GradebookEntry.student_account_id == student_id,
    ).first()
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gradebook entry not found or does not belong to you.",
        )
    if entry.completion_status in ("PASSED", "COMPLETED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This subject is already completed. No completion request is needed.",
        )

    existing = db.query(models.CompletionRequest).filter(
        models.CompletionRequest.gradebook_entry_id == data.gradebook_entry_id,
        models.CompletionRequest.workflow_state.notin_(["POSTED", "REJECTED"]),
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An active completion request already exists for this entry (ID: {existing.id}).",
        )

    initial_note = {
        "actor_id":   student_id,
        "actor_role": "STUDENT",
        "state":      "PENDING_FEE",
        "note":       data.student_note or "Completion request submitted.",
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    }
    req = models.CompletionRequest(
        student_account_id=student_id,
        gradebook_entry_id=data.gradebook_entry_id,
        workflow_state="PENDING_FEE",
        workflow_notes=[initial_note],
    )
    saved = repository.save_completion_request(db, req)

    audit_service.log_event(
        database_session=db,
        event_type="COMPLETION_REQUEST_SUBMITTED",
        actor_id=student_id,
        target_type="completion_request",
        target_id=saved.id,
        ip_address=ip_address,
        payload={"gradebook_entry_id": data.gradebook_entry_id},
    )
    return saved


def advance_completion_workflow(
    db: Session,
    request_id: int,
    actor_id: int,
    actor_email: str,
    actor_role: str,
    data: schemas.CompletionWorkflowAdvance,
    ip_address: Optional[str] = None,
) -> models.CompletionRequest:
    req = repository.fetch_completion_request_by_id(db, request_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Completion request not found.")

    transition    = (req.workflow_state, data.new_state)
    allowed_roles = _VALID_TRANSITIONS.get(transition)
    if allowed_roles is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transition: {req.workflow_state} → {data.new_state}.",
        )
    if actor_role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your role ({actor_role}) cannot perform this transition.",
        )

    if actor_role == "FACULTY":
        from src.modules.faculty.models import GradebookEntry
        entry = db.query(GradebookEntry).filter(
            GradebookEntry.grade_id == req.gradebook_entry_id,
            GradebookEntry.faculty_account_id == actor_id,
        ).first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This completion request is not assigned to you.",
            )
        if data.faculty_grade is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="faculty_grade is required when submitting a completion grade.",
            )
        req.faculty_final_grade  = data.faculty_grade
        req.faculty_submitted_at = datetime.now(timezone.utc)
        req.faculty_submitted_by = actor_id

    if data.new_state == "ROUTED_TO_FACULTY":
        req.fee_verified_by = actor_id
        req.fee_verified_at = datetime.now(timezone.utc)

    if data.new_state == "POSTED":
        if req.faculty_final_grade is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot post: faculty has not submitted a final grade yet.",
            )
        from src.modules.faculty.models import GradebookEntry
        entry = db.query(GradebookEntry).filter(GradebookEntry.grade_id == req.gradebook_entry_id).first()
        if entry:
            entry.final_grade       = req.faculty_final_grade
            entry.completion_status = "COMPLETED"
            entry.override_reason   = "INC completion — posted via Secretariat workflow"
        req.admin_posted_by = actor_id
        req.admin_posted_at = datetime.now(timezone.utc)

    if data.new_state == "REJECTED":
        if not data.rejection_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="rejection_reason is required when rejecting a completion request.",
            )
        req.rejected_by      = actor_id
        req.rejected_at      = datetime.now(timezone.utc)
        req.rejection_reason = data.rejection_reason

    req.workflow_state = data.new_state

    notes = list(req.workflow_notes or [])
    notes.append({
        "actor_id":   actor_id,
        "actor_role": actor_role,
        "state":      data.new_state,
        "note":       data.note,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
    })
    req.workflow_notes = notes

    db.commit()
    db.refresh(req)

    audit_service.log_event(
        database_session=db,
        event_type="COMPLETION_WORKFLOW_ADVANCED",
        actor_id=actor_id,
        actor_email=actor_email,
        target_type="completion_request",
        target_id=request_id,
        ip_address=ip_address,
        payload={"new_state": data.new_state, "actor_role": actor_role},
    )
    return req
