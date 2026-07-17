# backend-v2/src/modules/document_processing/schemas.py

from datetime import datetime
from typing import List, Any
from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────────────
# Existing schemas (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

class ScanInitiationResponse(BaseModel):
    secure_scan_token: str
    processing_status: str
    message: str


class ScanStatusReport(BaseModel):
    processing_status: str
    extracted_ai_data: str | None   = None
    confidence_score:  float | None = None
    error_message:     str | None   = None

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# HITL Verification Queue — new schemas
# ─────────────────────────────────────────────────────────────────────────────

class VerificationQueueItem(BaseModel):
    """
    Summary row returned by GET /documents/verification-queue.
    Intentionally omits extracted_ai_data to keep the list response lightweight.
    """
    secure_scan_token: str
    document_type:     str | None      = None
    confidence_score:  float | None    = None
    processing_status: str
    date_scanned:      datetime | None = None
    has_review_image:  bool               = False  # True if the source image is still on disk

    model_config = ConfigDict(from_attributes=True)


class SubjectCorrection(BaseModel):
    """Single corrected subject row."""
    code:  str   = Field(..., description="Subject code exactly as it appears on the COR, e.g. CS 101")
    name:  str   = Field(..., description="Full descriptive title of the subject")
    units: float = Field(..., description="Credit units as a number, e.g. 3.0")


class ExtractedDataCorrection(BaseModel):
    """
    The fields an admin/secretary can override inside extracted_data.
    All fields are optional — only provided fields are merged; others keep the AI value.
    """
    full_name:   str | None                  = None
    student_id:  str | None                  = None
    subjects:    List[SubjectCorrection] | None = None
    total_units: float | None                = None


class ManualCorrectionRequest(BaseModel):
    """Request body for PATCH /documents/verification/{token}/correct."""
    corrected_data: ExtractedDataCorrection
    reviewer_notes: str | None = Field(
        None,
        description="Optional note explaining what was changed and why, for the audit trail.",
    )


class ManualCorrectionResponse(BaseModel):
    """Response returned after a successful manual correction."""
    secure_scan_token: str
    processing_status: str
    message:           str
