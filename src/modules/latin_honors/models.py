from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from src.core.database_setup import Base


class DeanNote(Base):
    __tablename__ = "dean_notes"

    id = Column(Integer, primary_key=True, index=True)
    student_account_id = Column(
        Integer, ForeignKey("user_accounts.account_id"), index=True, nullable=False
    )
    message = Column(Text, nullable=False)
    written_by_admin_id = Column(
        Integer, ForeignKey("user_accounts.account_id"), nullable=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HonorsRating(Base):
    __tablename__ = "honors_ratings"

    id = Column(Integer, primary_key=True, index=True)
    student_account_id = Column(
        Integer, ForeignKey("user_accounts.account_id"), index=True, nullable=False
    )
    rater_session_token = Column(String(100), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "student_account_id", "rater_session_token",
            name="uq_honors_rating_token",
        ),
    )
