from sqlalchemy.orm import Session
from . import models


def save_completion_request(db: Session, req: models.CompletionRequest) -> models.CompletionRequest:
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def fetch_completion_request_by_id(db: Session, request_id: int) -> models.CompletionRequest | None:
    return (
        db.query(models.CompletionRequest)
        .filter(models.CompletionRequest.id == request_id)
        .first()
    )


def fetch_completion_requests(
    db: Session,
    state_filter: str | None = None,
    student_id: int | None = None,
) -> list[models.CompletionRequest]:
    query = db.query(models.CompletionRequest)
    if state_filter:
        query = query.filter(models.CompletionRequest.workflow_state == state_filter)
    if student_id:
        query = query.filter(models.CompletionRequest.student_account_id == student_id)
    return query.order_by(models.CompletionRequest.created_at.asc()).all()


def fetch_completion_requests_for_faculty(
    db: Session,
    faculty_account_id: int,
) -> list[models.CompletionRequest]:
    from src.modules.faculty.models import GradebookEntry
    return (
        db.query(models.CompletionRequest)
        .join(GradebookEntry, models.CompletionRequest.gradebook_entry_id == GradebookEntry.grade_id)
        .filter(
            GradebookEntry.faculty_account_id == faculty_account_id,
            models.CompletionRequest.workflow_state == "ROUTED_TO_FACULTY",
        )
        .order_by(models.CompletionRequest.created_at.asc())
        .all()
    )
