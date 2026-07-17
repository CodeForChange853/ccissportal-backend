from sqlalchemy.orm import Session
from . import models


def save_ojt_submission(db: Session, submission: models.OJTSubmission) -> models.OJTSubmission:
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def fetch_all_ojt_submissions(
    db: Session,
    status_filter: str | None = None,
) -> list[models.OJTSubmission]:
    query = db.query(models.OJTSubmission)
    if status_filter:
        query = query.filter(models.OJTSubmission.submission_status == status_filter)
    return query.order_by(models.OJTSubmission.submitted_at.asc()).all()


def fetch_ojt_submission_by_id(db: Session, submission_id: int) -> models.OJTSubmission | None:
    return (
        db.query(models.OJTSubmission)
        .filter(models.OJTSubmission.id == submission_id)
        .first()
    )


def fetch_latest_ojt_submission_for_student(
    db: Session,
    student_id: int,
) -> models.OJTSubmission | None:
    return (
        db.query(models.OJTSubmission)
        .filter(models.OJTSubmission.student_account_id == student_id)
        .order_by(models.OJTSubmission.submitted_at.desc())
        .first()
    )
