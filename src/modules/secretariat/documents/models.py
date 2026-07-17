from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from src.core.database_setup import Base


class DocumentRequest(Base):
    __tablename__ = "document_requests"

    id               = Column(Integer, primary_key=True, index=True)
    reference_number = Column(String(30), unique=True, index=True, nullable=False)

    requestor_account_id = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True, index=True)
    requestor_name       = Column(String(255), nullable=True)
    requestor_email      = Column(String(255), nullable=True)

    # CURRENT_STUDENT | ALUMNI | EXTERNAL
    requestor_type = Column(String(20), nullable=False, default="CURRENT_STUDENT")

    # TRANSCRIPT | CERTIFICATION | DIPLOMA_AUTH | GOOD_MORAL | ENROLLMENT_CERT | OTHER
    document_type  = Column(String(30), nullable=False)
    purpose        = Column(Text, nullable=False)
    document_notes = Column(String(500), nullable=True)

    # PENDING → PROCESSING → READY_FOR_PICKUP → RELEASED | REJECTED
    status = Column(String(25), nullable=False, default="PENDING", index=True)

    secretary_notes            = Column(String(500), nullable=True)
    processed_by_secretary_id  = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)
    processing_started_at      = Column(DateTime(timezone=True), nullable=True)
    ready_at                   = Column(DateTime(timezone=True), nullable=True)
    released_at                = Column(DateTime(timezone=True), nullable=True)
    rejected_at                = Column(DateTime(timezone=True), nullable=True)
    rejection_reason           = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
