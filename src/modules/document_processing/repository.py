# backend-v2/src/modules/document_processing/repository.py

import os
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from .models import DocumentScanResult

# ─────────────────────────────────────────────────────────────────────────────
# Confidence threshold — shared by repository (cache gate) and service (routing)
# Aligned with ScanDiffViewer.jsx green boundary (>= 80 % → "safe to approve")
# ─────────────────────────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD  = 0.80   # Above this → COMPLETED (auto-accepted, cached)
CONFIDENCE_FLOOR      = 0.50   # Below this → FAILED (re-upload required, not queued)
# Between CONFIDENCE_FLOOR and CONFIDENCE_THRESHOLD → NEEDS_REVIEW (human queue)


# ─────────────────────────────────────────────────────────────────────────────
# Core CRUD
# ─────────────────────────────────────────────────────────────────────────────

def create_initial_scan_record(
    database_session: Session,
    new_token: str,
    file_hash: str = None,
) -> DocumentScanResult:
    new_record = DocumentScanResult(
        secure_scan_token=new_token,
        processing_status="PROCESSING",
        file_hash=file_hash,
    )
    database_session.add(new_record)
    database_session.commit()
    return new_record


def fetch_scan_by_token(
    database_session: Session,
    token: str,
) -> DocumentScanResult | None:
    return database_session.query(DocumentScanResult).filter(
        DocumentScanResult.secure_scan_token == token
    ).first()


def fetch_successful_scan_by_hash(
    database_session: Session,
    target_hash: str,
    doc_type: str,
) -> DocumentScanResult | None:
    """
    Deduplication cache lookup.

    Priority 1 — MANUALLY_VERIFIED: an admin/secretary has put human eyes on
    this exact document and corrected it. This is the gold-standard result and
    always wins regardless of confidence score.

    Priority 2 — COMPLETED with confidence ≥ CONFIDENCE_THRESHOLD: a high-
    confidence AI extraction that passed the auto-accept gate.

    NEEDS_REVIEW records are intentionally excluded — a low-confidence result
    should never be silently reused; the student deserves a fresh attempt or
    admin review.
    """
    # Priority 1: Human-verified result
    verified = (
        database_session.query(DocumentScanResult)
        .filter(
            DocumentScanResult.file_hash == target_hash,
            DocumentScanResult.document_type == doc_type,
            DocumentScanResult.processing_status == "MANUALLY_VERIFIED",
        )
        .order_by(DocumentScanResult.date_scanned.desc())
        .first()
    )
    if verified:
        return verified

    # Priority 2: High-confidence AI result
    return (
        database_session.query(DocumentScanResult)
        .filter(
            DocumentScanResult.file_hash == target_hash,
            DocumentScanResult.document_type == doc_type,
            DocumentScanResult.processing_status == "COMPLETED",
            DocumentScanResult.confidence_score >= CONFIDENCE_THRESHOLD,
        )
        .order_by(DocumentScanResult.date_scanned.desc())
        .first()
    )


def update_scan_completion(
    database_session: Session,
    token: str,
    extracted_data: str = None,
    error_msg: str = None,
    confidence_score: float = None,
    document_type: str = None,
    status: str = None,           # Caller MUST pass the correct terminal status
    review_image_path: str = None,
) -> None:
    """
    Writes the final outcome of a scan to the database.

    IMPORTANT: `status` is no longer optional for success paths.
    service.py determines whether the scan is COMPLETED, NEEDS_REVIEW, or FAILED
    and passes it explicitly. This function no longer hardcodes "COMPLETED".
    """
    scan_record = fetch_scan_by_token(database_session, token)
    if not scan_record:
        return

    if error_msg:
        scan_record.processing_status = status or "FAILED"
        scan_record.error_message     = error_msg
    else:
        # ← Fixed: was hardcoded "COMPLETED" — now respects caller's status
        scan_record.processing_status = status or "COMPLETED"
        scan_record.extracted_ai_data = extracted_data
        if confidence_score is not None:
            scan_record.confidence_score = confidence_score
        if document_type is not None:
            scan_record.document_type = document_type
        if review_image_path is not None:
            scan_record.review_image_path = review_image_path

    database_session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Verification Queue (HITL)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_verification_queue(
    database_session: Session,
    skip: int = 0,
    limit: int = 50,
) -> list[DocumentScanResult]:
    """Returns paginated NEEDS_REVIEW records, oldest first (FIFO processing)."""
    return (
        database_session.query(DocumentScanResult)
        .filter(DocumentScanResult.processing_status == "NEEDS_REVIEW")
        .order_by(DocumentScanResult.date_scanned.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_verification_queue(database_session: Session) -> int:
    return (
        database_session.query(DocumentScanResult)
        .filter(DocumentScanResult.processing_status == "NEEDS_REVIEW")
        .count()
    )


def apply_manual_correction(
    database_session: Session,
    token: str,
    corrected_fields: dict,      # Only the fields to override inside extracted_data
    reviewer_id: int,
    reviewer_notes: str = None,
) -> DocumentScanResult | None:
    """
    Merges admin-corrected field values into the stored AI payload and marks the
    record as MANUALLY_VERIFIED.

    - Only fields explicitly included in corrected_fields are overwritten.
    - verification_result and ai_recommendation are cleared because they were
      derived from the (possibly wrong) AI-extracted subject codes; the enrollment
      service will re-run the prerequisite check on the next submission.
    - The retained review image is deleted after successful correction.
    """
    scan_record = fetch_scan_by_token(database_session, token)
    if not scan_record:
        return None

    # Merge corrected fields into existing payload
    if scan_record.extracted_ai_data:
        try:
            payload = json.loads(scan_record.extracted_ai_data)
        except (json.JSONDecodeError, TypeError):
            payload = {}
    else:
        payload = {}

    existing_extracted = payload.get("extracted_data", {}) or {}
    existing_extracted.update({k: v for k, v in corrected_fields.items() if v is not None})
    payload["extracted_data"]      = existing_extracted
    payload["verification_result"] = None   # Stale — cleared so enrollment re-checks
    payload["ai_recommendation"]   = None   # Stale — cleared so enrollment re-checks
    payload["manual_correction"]   = True   # Marker so downstream code knows this was human-reviewed

    scan_record.extracted_ai_data    = json.dumps(payload)
    scan_record.processing_status    = "MANUALLY_VERIFIED"
    scan_record.manually_reviewed_by = reviewer_id
    scan_record.manually_reviewed_at = datetime.now(timezone.utc)
    scan_record.reviewer_notes       = reviewer_notes

    # Clean up the retained image — no longer needed once verified
    if scan_record.review_image_path and os.path.exists(scan_record.review_image_path):
        try:
            os.remove(scan_record.review_image_path)
        except OSError:
            pass  # Non-fatal — file may have been manually cleaned already
    scan_record.review_image_path = None

    database_session.commit()
    return scan_record
