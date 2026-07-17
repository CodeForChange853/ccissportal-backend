from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import models, schemas, repository
from src.modules.enrollment.models import StudentProfile
from src.modules.audit import service as audit_service


def submit_ojt_documents(
    db: Session,
    student_id: int,
    submission_data: schemas.OJTSubmissionCreate,
    ip_address: Optional[str] = None,
) -> models.OJTSubmission:
    profile = db.query(StudentProfile).filter(
        StudentProfile.student_account_id == student_id
    ).first()

    if profile and profile.ojt_clearance_status == "CLEARED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your OJT clearance is already CLEARED. No further submission is needed.",
        )

    submission = models.OJTSubmission(
        student_account_id=student_id,
        moa_document_ref=submission_data.moa_document_ref,
        consent_form_ref=submission_data.consent_form_ref,
        medical_clearance_ref=submission_data.medical_clearance_ref,
        additional_notes=submission_data.additional_notes,
        submission_status="PENDING",
    )
    saved = repository.save_ojt_submission(db, submission)

    if profile:
        profile.ojt_clearance_status = "PENDING"
        db.commit()

    audit_service.log_event(
        database_session=db,
        event_type="OJT_SUBMISSION_RECEIVED",
        actor_id=student_id,
        target_type="ojt_submission",
        target_id=saved.id,
        ip_address=ip_address,
        payload={"student_id": student_id},
    )
    return saved


def process_ojt_verification(
    db: Session,
    submission_id: int,
    secretary_id: int,
    secretary_email: str,
    verification_data: schemas.OJTVerificationUpdate,
    ip_address: Optional[str] = None,
) -> models.OJTSubmission:
    if verification_data.decision not in ("VERIFIED", "REJECTED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be VERIFIED or REJECTED.",
        )

    submission = repository.fetch_ojt_submission_by_id(db, submission_id)
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OJT submission not found.")

    if submission.submission_status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This submission has already been processed (status: {submission.submission_status}).",
        )

    submission.submission_status        = verification_data.decision
    submission.secretary_notes          = verification_data.secretary_notes
    submission.verified_by_secretary_id = secretary_id
    submission.verified_at              = datetime.now(timezone.utc)

    new_clearance = "CLEARED" if verification_data.decision == "VERIFIED" else "BLOCKED"
    profile = db.query(StudentProfile).filter(
        StudentProfile.student_account_id == submission.student_account_id
    ).first()
    if profile:
        profile.ojt_clearance_status = new_clearance

    db.commit()
    db.refresh(submission)

    event_type = "OJT_CLEARED" if verification_data.decision == "VERIFIED" else "OJT_REJECTED"
    audit_service.log_event(
        database_session=db,
        event_type=event_type,
        actor_id=secretary_id,
        actor_email=secretary_email,
        target_type="ojt_submission",
        target_id=submission_id,
        ip_address=ip_address,
        payload={
            "student_id":           submission.student_account_id,
            "decision":             verification_data.decision,
            "new_clearance_status": new_clearance,
        },
    )
    return submission


def get_ojt_clearance_status(
    db: Session,
    student_id: int,
) -> schemas.OJTClearanceStatusResponse:
    profile = db.query(StudentProfile).filter(
        StudentProfile.student_account_id == student_id
    ).first()
    clearance = profile.ojt_clearance_status if profile else "NOT_REQUIRED"

    latest = repository.fetch_latest_ojt_submission_for_student(db, student_id)

    return schemas.OJTClearanceStatusResponse(
        student_account_id=student_id,
        ojt_clearance_status=clearance,
        latest_submission=(
            schemas.OJTSubmissionResponse.model_validate(latest) if latest else None
        ),
    )
