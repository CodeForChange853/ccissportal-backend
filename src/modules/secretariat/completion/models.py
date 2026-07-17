from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, JSON
from sqlalchemy.sql import func
from src.core.database_setup import Base


class CompletionRequest(Base):
    __tablename__ = "completion_requests"

    id = Column(Integer, primary_key=True, index=True)

    student_account_id = Column(Integer, ForeignKey("user_accounts.account_id"), index=True, nullable=False)
    gradebook_entry_id = Column(Integer, ForeignKey("gradebook_entries.grade_id"), index=True, nullable=False)

    # PENDING_FEE → ROUTED_TO_FACULTY → AWAITING_ADMIN_POSTING → POSTED | REJECTED
    workflow_state = Column(String(30), nullable=False, default="PENDING_FEE", index=True)

    fee_verified_by = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)
    fee_verified_at = Column(DateTime(timezone=True), nullable=True)

    faculty_final_grade  = Column(Float, nullable=True)
    faculty_submitted_at = Column(DateTime(timezone=True), nullable=True)
    faculty_submitted_by = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)

    admin_posted_by = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)
    admin_posted_at = Column(DateTime(timezone=True), nullable=True)

    rejected_by      = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)
    rejected_at      = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(String(500), nullable=True)

    # [{actor_id, actor_role, state, note, ts}]
    workflow_notes = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
