from sqlalchemy.orm import Session
from . import models


def save_mapping_draft(db: Session, draft: models.SubjectMappingDraft) -> models.SubjectMappingDraft:
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def fetch_mapping_draft_by_id(db: Session, draft_id: int) -> models.SubjectMappingDraft | None:
    return (
        db.query(models.SubjectMappingDraft)
        .filter(models.SubjectMappingDraft.id == draft_id)
        .first()
    )


def fetch_all_mapping_drafts(
    db: Session,
    status_filter: str | None = None,
    student_id: int | None = None,
) -> list[models.SubjectMappingDraft]:
    query = db.query(models.SubjectMappingDraft)
    if status_filter:
        query = query.filter(models.SubjectMappingDraft.status == status_filter)
    if student_id:
        query = query.filter(models.SubjectMappingDraft.student_account_id == student_id)
    return query.order_by(models.SubjectMappingDraft.created_at.desc()).all()


def delete_mapping_draft(db: Session, draft: models.SubjectMappingDraft) -> None:
    db.delete(draft)
    db.commit()
