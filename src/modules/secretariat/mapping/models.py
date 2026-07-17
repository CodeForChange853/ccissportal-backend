from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from src.core.database_setup import Base


class SubjectMappingDraft(Base):
    __tablename__ = "subject_mapping_drafts"

    id = Column(Integer, primary_key=True, index=True)

    student_account_id       = Column(Integer, ForeignKey("user_accounts.account_id"), index=True, nullable=False)
    prepared_by_secretary_id = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=False)

    previous_institution = Column(String(255), nullable=False)
    previous_program     = Column(String(255), nullable=False)

    # [{previous_subject_code, previous_subject_name, previous_credit_units,
    #   ccis_subject_id, recommended_action: CREDIT|VALIDATE|REJECT}]
    mapping_entries = Column(JSON, nullable=False, default=list)

    # DRAFT | SUBMITTED_FOR_APPROVAL | APPROVED | REJECTED
    status = Column(String(30), nullable=False, default="DRAFT", index=True)

    admin_notes          = Column(String(500), nullable=True)
    approved_by_admin_id = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)
    approved_at          = Column(DateTime(timezone=True), nullable=True)
    rejected_by_admin_id = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)
    rejected_at          = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
