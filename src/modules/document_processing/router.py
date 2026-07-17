import uuid
import os
import json
import hashlib

from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import schemas, service, repository
from src.core.database_setup import get_database_session
from src.core.security import get_current_user, get_optional_current_user, require_admin_or_secretary
from src.modules.auth.models import UserAccount

document_router = APIRouter(
    prefix="/documents",
    tags=["AI Document Scanning"]
)

os.makedirs("temp_uploads", exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Existing endpoints (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

@document_router.post("/scan/{document_type}", response_model=schemas.ScanInitiationResponse)
def upload_and_scan_document(
    request: Request,
    document_type: str,
    background_tasks: BackgroundTasks,
    uploaded_file: UploadFile = File(...),
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount | None = Depends(get_optional_current_user),
):
    # ── 1. Validate File Size (5MB Limit) ─────────────────────────────
    MAX_SIZE = 5 * 1024 * 1024  # 5MB
    uploaded_file.file.seek(0, os.SEEK_END)
    file_size = uploaded_file.file.tell()
    uploaded_file.file.seek(0)

    if file_size > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({file_size} bytes). Maximum allowed is 5MB."
        )

    # ── 2. Validate MIME Type ──────────────────────────────────────────
    ALLOWED_TYPES = ["image/jpeg", "image/png", "application/pdf"]
    if uploaded_file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Invalid file type '{uploaded_file.content_type}'. Only JPG, PNG, and PDF are allowed."
        )

    # ── 3. Calculate File Hash (SHA-256) for Deduplication Cache ──────
    file_content = uploaded_file.file.read()
    file_hash    = hashlib.sha256(file_content).hexdigest()
    uploaded_file.file.seek(0)

    # ── 4. Check Deduplication Cache (Fast Reuse Path) ────────────────
    # fetch_successful_scan_by_hash prioritises MANUALLY_VERIFIED, then
    # COMPLETED records with confidence >= CONFIDENCE_THRESHOLD (0.80).
    existing_scan = repository.fetch_successful_scan_by_hash(database_session, file_hash, document_type)

    if existing_scan:
        new_token = str(uuid.uuid4())
        repository.create_initial_scan_record(database_session, new_token, file_hash)
        repository.update_scan_completion(
            database_session=database_session,
            token=new_token,
            extracted_data=existing_scan.extracted_ai_data,
            confidence_score=existing_scan.confidence_score,
            document_type=document_type,
            status="COMPLETED",
        )
        return schemas.ScanInitiationResponse(
            secure_scan_token=new_token,
            processing_status="COMPLETED",
            message="Document fingerprint recognized. Reusing previous verified analysis.",
        )

    # ── 5. Standard Background Processing Path ────────────────────────
    secure_token   = str(uuid.uuid4())
    temp_file_path = f"temp_uploads/{secure_token}_{uploaded_file.filename}"

    with open(temp_file_path, "wb") as buffer:
        buffer.write(file_content)

    repository.create_initial_scan_record(database_session, secure_token, file_hash)

    background_tasks.add_task(
        service.execute_background_ai_scan,
        temp_file_path,
        secure_token,
        document_type,
        current_user.account_id if current_user else None,
        current_user.account_id if current_user else None,
        current_user.email_address if current_user else None,
        request.client.host if request.client else None,
    )

    return schemas.ScanInitiationResponse(
        secure_scan_token=secure_token,
        processing_status="PROCESSING",
        message="Your document is safely uploaded and is currently being analyzed.",
    )


@document_router.get("/status/{scan_token}", response_model=schemas.ScanStatusReport)
def check_scan_status(
    scan_token: str,
    database_session: Session = Depends(get_database_session),
):
    scan_record = repository.fetch_scan_by_token(database_session, scan_token)
    if scan_record is None:
        raise HTTPException(status_code=404, detail="Scan token not found.")

    return schemas.ScanStatusReport(
        processing_status=scan_record.processing_status,
        extracted_ai_data=scan_record.extracted_ai_data,
        error_message=scan_record.error_message,
    )


@document_router.get("/verification/{scan_token}")
def get_verification_score_card(
    scan_token: str,
    database_session: Session = Depends(get_database_session),
):
    scan_record = repository.fetch_scan_by_token(database_session, scan_token)
    if scan_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No scan record found for token '{scan_token}'.",
        )

    extracted_data       = None
    confidence_breakdown = None
    model_used           = None
    verification_result  = None
    ai_recommendation    = None

    if scan_record.extracted_ai_data:
        try:
            payload              = json.loads(scan_record.extracted_ai_data)
            extracted_data       = payload.get("extracted_data")
            model_used           = payload.get("model_used")
            confidence_breakdown = payload.get("confidence_breakdown")
            verification_result  = payload.get("verification_result")
            ai_recommendation    = payload.get("ai_recommendation")
        except (json.JSONDecodeError, TypeError):
            extracted_data = None

    return {
        "scan_token":           scan_token,
        "document_type":        scan_record.document_type,
        "processing_status":    scan_record.processing_status,
        "confidence_score":     scan_record.confidence_score,
        "confidence_breakdown": confidence_breakdown,
        "extracted_data":       extracted_data,
        "model_used":           model_used,
        "verification_result":  verification_result,
        "ai_recommendation":    ai_recommendation,
        "error_message":        scan_record.error_message,
    }


# ─────────────────────────────────────────────────────────────────────────────
# HITL Verification Queue — new endpoints (admin / secretary only)
# ─────────────────────────────────────────────────────────────────────────────

@document_router.get("/verification-queue", response_model=list[schemas.VerificationQueueItem])
def get_verification_queue(
    response: Response,                   # FastAPI injects this; we use it to set X-Total-Count
    skip: int = 0,
    limit: int = 50,
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(require_admin_or_secretary),
):
    """
    Returns paginated NEEDS_REVIEW scan records for the human verification queue.
    Results are ordered oldest-first (FIFO) so the longest-waiting students are
    reviewed first.

    Custom response header: X-Total-Count — total number of pending items.
    """
    records = repository.fetch_verification_queue(database_session, skip=skip, limit=limit)
    total   = repository.count_verification_queue(database_session)

    response.headers["X-Total-Count"] = str(total)

    return [
        schemas.VerificationQueueItem(
            secure_scan_token=r.secure_scan_token,
            document_type=r.document_type,
            confidence_score=r.confidence_score,
            processing_status=r.processing_status,
            date_scanned=r.date_scanned,
            has_review_image=bool(
                r.review_image_path and os.path.exists(r.review_image_path)
            ),
        )
        for r in records
    ]


@document_router.get("/verification/{scan_token}/image")
def get_review_image(
    scan_token: str,
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(require_admin_or_secretary),
):
    """
    Serves the retained source document image for a NEEDS_REVIEW scan.
    Only available while the record is in NEEDS_REVIEW status — the file is
    deleted automatically when apply_manual_correction() runs.

    The frontend must fetch this with the Authorization header (Bearer token).
    Use the blob-fetch pattern; a plain <img src="..."> will not send the token.
    """
    scan_record = repository.fetch_scan_by_token(database_session, scan_token)
    if scan_record is None:
        raise HTTPException(status_code=404, detail="Scan token not found.")

    if not scan_record.review_image_path:
        raise HTTPException(
            status_code=404,
            detail="No review image is stored for this scan. It may have already been verified or was never retained.",
        )

    if not os.path.exists(scan_record.review_image_path):
        raise HTTPException(
            status_code=404,
            detail="Review image file was not found on disk. It may have been cleaned up already.",
        )

    return FileResponse(
        path=scan_record.review_image_path,
        media_type="image/jpeg",
        filename=f"review_{scan_token}.jpg",
    )


@document_router.patch(
    "/verification/{scan_token}/correct",
    response_model=schemas.ManualCorrectionResponse,
)
def apply_manual_correction(
    scan_token: str,
    correction: schemas.ManualCorrectionRequest,
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(require_admin_or_secretary),
):
    """
    Allows an admin or secretary to correct inaccurate AI-extracted fields and
    mark the document as MANUALLY_VERIFIED.

    Security constraints enforced here:
    - Only NEEDS_REVIEW records can be corrected (prevents silent re-editing
      of already-approved documents without an explicit reopen flow).
    - verification_result and ai_recommendation are automatically cleared by
      apply_manual_correction() so the enrollment service re-runs the
      prerequisite check with the corrected subject codes.
    """
    scan_record = repository.fetch_scan_by_token(database_session, scan_token)
    if scan_record is None:
        raise HTTPException(status_code=404, detail="Scan token not found.")

    if scan_record.processing_status != "NEEDS_REVIEW":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot correct a scan with status '{scan_record.processing_status}'. "
                "Only NEEDS_REVIEW records can be manually corrected."
            ),
        )

    # Build corrected_fields — only include values the admin explicitly provided
    corrected    = correction.corrected_data
    corrected_fields: dict = {}

    if corrected.full_name   is not None: corrected_fields["full_name"]   = corrected.full_name
    if corrected.student_id  is not None: corrected_fields["student_id"]  = corrected.student_id
    if corrected.total_units is not None: corrected_fields["total_units"] = corrected.total_units
    if corrected.subjects    is not None:
        corrected_fields["subjects"] = [s.model_dump() for s in corrected.subjects]

    updated = repository.apply_manual_correction(
        database_session=database_session,
        token=scan_token,
        corrected_fields=corrected_fields,
        reviewer_id=current_user.account_id,
        reviewer_notes=correction.reviewer_notes,
    )

    if updated is None:
        raise HTTPException(status_code=500, detail="Correction failed — record not found after update.")

    # Audit trail
    from src.modules.audit import service as audit_service
    audit_service.log_event(
        database_session=database_session,
        event_type="DOCUMENT_MANUALLY_VERIFIED",
        actor_id=current_user.account_id,
        actor_email=current_user.email_address,
        target_type="document",
        target_id=scan_token,
        payload={
            "corrected_fields": list(corrected_fields.keys()),
            "reviewer_notes":   correction.reviewer_notes,
            "document_type":    scan_record.document_type,
        },
    )

    return schemas.ManualCorrectionResponse(
        secure_scan_token=scan_token,
        processing_status="MANUALLY_VERIFIED",
        message=(
            "Document data corrected and marked as verified. "
            "The prerequisite check will re-run when the student submits their enrollment."
        ),
    )
