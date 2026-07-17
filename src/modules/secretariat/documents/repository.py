from sqlalchemy.orm import Session
from . import models


def save_document_request(db: Session, req: models.DocumentRequest) -> models.DocumentRequest:
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def fetch_document_request_by_id(db: Session, request_id: int) -> models.DocumentRequest | None:
    return (
        db.query(models.DocumentRequest)
        .filter(models.DocumentRequest.id == request_id)
        .first()
    )


def fetch_document_request_by_reference(db: Session, reference_number: str) -> models.DocumentRequest | None:
    return (
        db.query(models.DocumentRequest)
        .filter(models.DocumentRequest.reference_number == reference_number)
        .first()
    )


def fetch_document_requests(
    db: Session,
    status_filter: str | None = None,
    requestor_account_id: int | None = None,
    requestor_type: str | None = None,
) -> list[models.DocumentRequest]:
    query = db.query(models.DocumentRequest)
    if status_filter:
        query = query.filter(models.DocumentRequest.status == status_filter)
    if requestor_account_id:
        query = query.filter(models.DocumentRequest.requestor_account_id == requestor_account_id)
    if requestor_type:
        query = query.filter(models.DocumentRequest.requestor_type == requestor_type)
    return query.order_by(models.DocumentRequest.created_at.asc()).all()
