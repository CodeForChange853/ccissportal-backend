from sqlalchemy.orm import Session
from . import models


def save_petition(db: Session, petition: models.SubjectPetition) -> models.SubjectPetition:
    db.add(petition)
    db.commit()
    db.refresh(petition)
    return petition


def fetch_petition_by_id(db: Session, petition_id: int) -> models.SubjectPetition | None:
    return (
        db.query(models.SubjectPetition)
        .filter(models.SubjectPetition.id == petition_id)
        .first()
    )


def fetch_petitions(
    db: Session,
    status_filter: str | None = None,
    student_id: int | None = None,
    petition_type: str | None = None,
) -> list[models.SubjectPetition]:
    query = db.query(models.SubjectPetition)
    if status_filter:
        query = query.filter(models.SubjectPetition.status == status_filter)
    if student_id:
        query = query.filter(models.SubjectPetition.student_account_id == student_id)
    if petition_type:
        query = query.filter(models.SubjectPetition.petition_type == petition_type)
    return query.order_by(models.SubjectPetition.created_at.asc()).all()
