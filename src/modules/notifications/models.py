from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from src.core.database_setup import Base


class Notification(Base):

    __tablename__ = "notifications"

    notification_id = Column(Integer, primary_key=True, index=True)
    recipient_account_id = Column(
        Integer,
        ForeignKey("user_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(120), nullable=False)
    message = Column(String(500), nullable=False)
    notif_type = Column(String(30), nullable=False)
    is_read = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_notifications_recipient_read_created",
            "recipient_account_id",
            "is_read",
            "created_at",
        ),
    )
