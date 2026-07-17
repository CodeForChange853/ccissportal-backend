import secrets
import string
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import models, schemas, repository
from src.modules.audit import service as audit_service

_VALID_DOCUMENT_TYPES = {
    "TRANSCRIPT", "CERTIFICATION", "DIPLOMA_AUTH",
    "GOOD_MORAL", "ENROLLMENT_CERT", "OTHER",
}
_VALID_REQUESTOR_TYPES = {"CURRENT_STUDENT", "ALUMNI", "EXTERNAL"}

_DOC_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "PENDING":          {"PROCESSING", "REJECTED"},
    "PROCESSING":       {"READY_FOR_PICKUP", "REJECTED"},
    "READY_FOR_PICKUP": {"RELEASED", "REJECTED"},
}


def _generate_reference_number() -> str:
    date_part   = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"DOCREQ-{date_part}-{random_part}"


def submit_document_request(
    db: Session,
    requestor_id: int,
    data: schemas.DocumentRequestCreate,
    ip_address: Optional[str] = None,
) -> models.DocumentRequest:
    if data.document_type not in _VALID_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document_type. Must be one of: {', '.join(sorted(_VALID_DOCUMENT_TYPES))}.",
        )
    if data.requestor_type not in _VALID_REQUESTOR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid requestor_type. Must be one of: {', '.join(sorted(_VALID_REQUESTOR_TYPES))}.",
        )

    ref = _generate_reference_number()
    req = models.DocumentRequest(
        reference_number=ref,
        requestor_account_id=requestor_id,
        requestor_type=data.requestor_type,
        document_type=data.document_type,
        purpose=data.purpose,
        document_notes=data.document_notes,
        status="PENDING",
    )
    saved = repository.save_document_request(db, req)

    audit_service.log_event(
        database_session=db,
        event_type="DOCUMENT_REQUEST_SUBMITTED",
        actor_id=requestor_id,
        target_type="document_request",
        target_id=saved.id,
        ip_address=ip_address,
        payload={"document_type": data.document_type, "reference": ref},
    )
    return saved


def submit_external_document_request(
    db: Session,
    secretary_id: int,
    secretary_email: str,
    data: schemas.ExternalDocumentRequestCreate,
    ip_address: Optional[str] = None,
) -> models.DocumentRequest:
    if data.document_type not in _VALID_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document_type. Must be one of: {', '.join(sorted(_VALID_DOCUMENT_TYPES))}.",
        )
    if data.requestor_type not in ("ALUMNI", "EXTERNAL"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="External requests must use requestor_type ALUMNI or EXTERNAL.",
        )

    ref = _generate_reference_number()
    req = models.DocumentRequest(
        reference_number=ref,
        requestor_name=data.requestor_name,
        requestor_email=data.requestor_email,
        requestor_type=data.requestor_type,
        document_type=data.document_type,
        purpose=data.purpose,
        document_notes=data.document_notes,
        status="PENDING",
    )
    saved = repository.save_document_request(db, req)

    audit_service.log_event(
        database_session=db,
        event_type="DOCUMENT_REQUEST_SUBMITTED_EXTERNAL",
        actor_id=secretary_id,
        actor_email=secretary_email,
        target_type="document_request",
        target_id=saved.id,
        ip_address=ip_address,
        payload={
            "document_type":  data.document_type,
            "reference":      ref,
            "requestor_name": data.requestor_name,
            "requestor_type": data.requestor_type,
        },
    )
    return saved


def advance_document_request_status(
    db: Session,
    request_id: int,
    data: schemas.DocumentStatusAdvance,
    secretary_id: int,
    secretary_email: str,
    ip_address: Optional[str] = None,
) -> models.DocumentRequest:
    req = repository.fetch_document_request_by_id(db, request_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document request not found.")

    allowed_next = _DOC_STATUS_TRANSITIONS.get(req.status)
    if allowed_next is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is in a terminal state ({req.status}) and cannot be advanced.",
        )
    if data.new_status not in allowed_next:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transition: {req.status} → {data.new_status}. Allowed: {', '.join(allowed_next)}.",
        )

    now = datetime.now(timezone.utc)
    if data.new_status == "PROCESSING":
        req.processing_started_at = now
    elif data.new_status == "READY_FOR_PICKUP":
        req.ready_at = now
    elif data.new_status == "RELEASED":
        req.released_at = now
    elif data.new_status == "REJECTED":
        if not data.rejection_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="rejection_reason is required when rejecting a document request.",
            )
        req.rejection_reason = data.rejection_reason
        req.rejected_at      = now

    req.status = data.new_status
    if data.secretary_notes:
        req.secretary_notes = data.secretary_notes
    req.processed_by_secretary_id = secretary_id

    db.commit()
    db.refresh(req)

    audit_service.log_event(
        database_session=db,
        event_type="DOCUMENT_REQUEST_STATUS_ADVANCED",
        actor_id=secretary_id,
        actor_email=secretary_email,
        target_type="document_request",
        target_id=request_id,
        ip_address=ip_address,
        payload={"new_status": data.new_status, "reference": req.reference_number},
    )
    return req


def track_document_request(db: Session, reference_number: str) -> models.DocumentRequest:
    req = repository.fetch_document_request_by_reference(db, reference_number)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No request found with this reference number.")
    return req
