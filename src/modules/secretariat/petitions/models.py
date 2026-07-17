from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from src.core.database_setup import Base


class SubjectPetition(Base):
    __tablename__ = "subject_petitions"

    id = Column(Integer, primary_key=True, index=True)

    student_account_id = Column(Integer, ForeignKey("user_accounts.account_id"), index=True, nullable=False)

    # OVERLOAD | SUBSTITUTE | LATE_ADD | CROSS_ENROLLMENT
    petition_type = Column(String(30), nullable=False, index=True)

    subject_id = Column(Integer, ForeignKey("curriculum_subjects.subject_id"), index=True, nullable=False)
    substitute_for_subject_id = Column(Integer, ForeignKey("curriculum_subjects.subject_id"), nullable=True)

    reason = Column(Text, nullable=False)

    # PENDING → SECRETARY_ENDORSED | SECRETARY_REJECTED → ADMIN_APPROVED | ADMIN_REJECTED
    status = Column(String(30), nullable=False, default="PENDING", index=True)

    secretary_notes    = Column(String(500), nullable=True)
    secretary_id       = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)
    secretary_acted_at = Column(DateTime(timezone=True), nullable=True)

    admin_notes    = Column(String(500), nullable=True)
    admin_id       = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)
    admin_acted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
