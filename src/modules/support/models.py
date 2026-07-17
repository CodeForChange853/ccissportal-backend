from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.sql import func
from src.core.database_setup import Base

class SupportTicket(Base):
    """Stores student support requests routed by student-selected department."""
    __tablename__ = "support_tickets"

    ticket_id = Column(Integer, primary_key=True, index=True)

    student_account_id = Column(Integer, ForeignKey("user_accounts.account_id"), index=True, nullable=False)

    department = Column(String(50), index=True, nullable=False, default="GENERAL")
    issue_subject = Column(String(200), nullable=False)
    issue_description = Column(Text, nullable=False)
    resolution_note = Column(Text, nullable=True)

    was_manually_rerouted = Column(Boolean, default=False, nullable=False)

    ticket_status = Column(String(50), default="OPEN", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SystemAnnouncement(Base):
    """Stores professional system status updates, incidents, and maintenance logs."""
    __tablename__ = "system_announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    type = Column(String(50), default="announcement") # incident, maintenance, announcement
    status = Column(String(50), default="ACTIVE")    # ACTIVE, RESOLVED
    created_at = Column(DateTime(timezone=True), server_default=func.now())