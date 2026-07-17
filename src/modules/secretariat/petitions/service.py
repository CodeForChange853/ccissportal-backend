from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import models, schemas, repository
from src.modules.audit import service as audit_service

_VALID_PETITION_TYPES = {"OVERLOAD", "SUBSTITUTE", "LATE_ADD", "CROSS_ENROLLMENT"}


def submit_petition(
    db: Session,
    student_id: int,
    data: schemas.SubjectPetitionCreate,
    ip_address: Optional[str] = None,
) -> models.SubjectPetition:
    if data.petition_type not in _VALID_PETITION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid petition_type. Must be one of: {', '.join(sorted(_VALID_PETITION_TYPES))}.",
        )

    from src.modules.enrollment.models import CurriculumSubject
    subject = db.query(CurriculumSubject).filter(CurriculumSubject.subject_id == data.subject_id).first()
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found in the curriculum.")

    if data.petition_type == "SUBSTITUTE" and data.substitute_for_subject_id:
        sub_for = db.query(CurriculumSubject).filter(
            CurriculumSubject.subject_id == data.substitute_for_subject_id
        ).first()
        if not sub_for:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="substitute_for_subject_id does not match any curriculum subject.",
            )

    existing = db.query(models.SubjectPetition).filter(
        models.SubjectPetition.student_account_id == student_id,
        models.SubjectPetition.subject_id == data.subject_id,
        models.SubjectPetition.status.notin_(["ADMIN_APPROVED", "ADMIN_REJECTED", "SECRETARY_REJECTED"]),
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You already have an open petition for this subject (ID: {existing.id}).",
        )

    petition = models.SubjectPetition(
        student_account_id=student_id,
        petition_type=data.petition_type,
        subject_id=data.subject_id,
        substitute_for_subject_id=data.substitute_for_subject_id,
        reason=data.reason,
        status="PENDING",
    )
    saved = repository.save_petition(db, petition)

    audit_service.log_event(
        database_session=db,
        event_type="PETITION_SUBMITTED",
        actor_id=student_id,
        target_type="subject_petition",
        target_id=saved.id,
        ip_address=ip_address,
        payload={"petition_type": data.petition_type, "subject_id": data.subject_id},
    )
    return saved


def act_on_petition_as_secretary(
    db: Session,
    petition_id: int,
    data: schemas.SecretaryPetitionAction,
    secretary_id: int,
    secretary_email: str,
    ip_address: Optional[str] = None,
) -> models.SubjectPetition:
    if data.decision not in ("ENDORSE", "REJECT"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Decision must be ENDORSE or REJECT.")

    petition = repository.fetch_petition_by_id(db, petition_id)
    if not petition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Petition not found.")
    if petition.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PENDING petitions can be acted on by Secretary (current: {petition.status}).",
        )

    now = datetime.now(timezone.utc)
    petition.secretary_id       = secretary_id
    petition.secretary_notes    = data.secretary_notes
    petition.secretary_acted_at = now
    petition.status = "SECRETARY_ENDORSED" if data.decision == "ENDORSE" else "SECRETARY_REJECTED"

    db.commit()
    db.refresh(petition)

    audit_service.log_event(
        database_session=db,
        event_type="PETITION_SECRETARY_ACTION",
        actor_id=secretary_id,
        actor_email=secretary_email,
        target_type="subject_petition",
        target_id=petition_id,
        ip_address=ip_address,
        payload={"decision": data.decision, "student_id": petition.student_account_id, "new_status": petition.status},
    )
    return petition


def act_on_petition_as_admin(
    db: Session,
    petition_id: int,
    data: schemas.AdminPetitionDecision,
    admin_id: int,
    admin_email: str,
    ip_address: Optional[str] = None,
) -> models.SubjectPetition:
    if data.decision not in ("APPROVE", "REJECT"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Decision must be APPROVE or REJECT.")

    petition = repository.fetch_petition_by_id(db, petition_id)
    if not petition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Petition not found.")
    if petition.status != "SECRETARY_ENDORSED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only SECRETARY_ENDORSED petitions can be decided by Admin (current: {petition.status}).",
        )

    now = datetime.now(timezone.utc)
    petition.admin_id       = admin_id
    petition.admin_notes    = data.admin_notes
    petition.admin_acted_at = now
    petition.status = "ADMIN_APPROVED" if data.decision == "APPROVE" else "ADMIN_REJECTED"

    if data.decision == "APPROVE":
        from src.modules.faculty.models import GradebookEntry
        credited = GradebookEntry(
            student_account_id=petition.student_account_id,
            curriculum_subject_id=petition.subject_id,
            faculty_account_id=admin_id,
            completion_status="IN PROGRESS",
            override_reason=f"Subject added via approved {petition.petition_type} petition (ID: {petition_id})",
        )
        db.add(credited)

    db.commit()
    db.refresh(petition)

    audit_service.log_event(
        database_session=db,
        event_type="PETITION_ADMIN_DECISION",
        actor_id=admin_id,
        actor_email=admin_email,
        target_type="subject_petition",
        target_id=petition_id,
        ip_address=ip_address,
        payload={
            "decision":   data.decision,
            "student_id": petition.student_account_id,
            "subject_id": petition.subject_id,
            "new_status": petition.status,
        },
    )
    return petition


def get_petition_by_id(db: Session, petition_id: int) -> models.SubjectPetition:
    petition = repository.fetch_petition_by_id(db, petition_id)
    if not petition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Petition not found.")
    return petition
