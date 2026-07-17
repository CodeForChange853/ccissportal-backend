# backend-v2/src/modules/document_processing/models.py

from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from sqlalchemy.sql import func
from src.core.database_setup import Base


class DocumentScanResult(Base):
    """
    Stores the result of every AI document scan.

    processing_status lifecycle:
        PROCESSING       — background task is running
        COMPLETED        — confidence ≥ 0.80; cached; safe to auto-accept
        NEEDS_REVIEW     — confidence 0.50–0.79; held in human verification queue
        MANUALLY_VERIFIED — an admin/secretary corrected and approved the data
        FAILED           — confidence < 0.50, or AI returned unusable data; student must re-upload
        ERROR            — unexpected exception or API outage during scan
    """

    __tablename__ = "document_scan_results"

    scan_id           = Column(Integer, primary_key=True, index=True)
    secure_scan_token = Column(String(255), unique=True, index=True, nullable=False)
    processing_status = Column(String(50), default="PROCESSING", index=True)
    extracted_ai_data = Column(Text, nullable=True)
    error_message     = Column(Text, nullable=True)
    confidence_score  = Column(Float, nullable=True)
    document_type     = Column(String(10), nullable=True)          # "ID" or "COR"
    file_hash         = Column(String(64), index=True, nullable=True)  # SHA-256 dedup fingerprint
    date_scanned      = Column(DateTime(timezone=True), server_default=func.now())

    # ── Manual review fields (populated when processing_status = NEEDS_REVIEW or MANUALLY_VERIFIED)
    review_image_path    = Column(String(512), nullable=True)   # Absolute path in review_queue/
    manually_reviewed_by = Column(Integer, nullable=True)       # UserAccount.account_id of reviewer
    manually_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewer_notes       = Column(Text, nullable=True)
