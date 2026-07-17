from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from src.core.database_setup import Base


class OJTSubmission(Base):
    __tablename__ = "ojt_submissions"

    id = Column(Integer, primary_key=True, index=True)
    student_account_id = Column(
        Integer, ForeignKey("user_accounts.account_id"), index=True, nullable=False
    )

    moa_document_ref      = Column(String(500), nullable=True)
    consent_form_ref      = Column(String(500), nullable=True)
    medical_clearance_ref = Column(String(500), nullable=True)
    additional_notes      = Column(String(1000), nullable=True)

    # PENDING | VERIFIED | REJECTED
    submission_status = Column(String(20), default="PENDING", nullable=False, index=True)

    secretary_notes = Column(String(500), nullable=True)

    verified_by_secretary_id = Column(
        Integer, ForeignKey("user_accounts.account_id"), nullable=True
    )
    verified_at  = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
