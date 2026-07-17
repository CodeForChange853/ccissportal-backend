from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Text, ForeignKey
from sqlalchemy.sql import func
from src.core.database_setup import Base


class StudentOrganization(Base):
    __tablename__ = "student_organizations"

    id          = Column(Integer, primary_key=True, index=True)
    org_name    = Column(String(255), unique=True, nullable=False, index=True)
    org_acronym = Column(String(20), nullable=True)

    # ACADEMIC | CULTURAL | SPORTS | RELIGIOUS | SERVICE | OTHER
    org_type    = Column(String(30), nullable=False, default="OTHER")
    description = Column(Text, nullable=True)

    adviser_account_id      = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)
    president_account_id    = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)
    submitted_by_account_id = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=False)

    # PENDING | RECOGNIZED | SUSPENDED | DISSOLVED
    status          = Column(String(20), nullable=False, default="PENDING", index=True)
    secretary_notes = Column(String(500), nullable=True)
    processed_by    = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)
    processed_at    = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Facility(Base):
    __tablename__ = "facilities"

    id            = Column(Integer, primary_key=True, index=True)
    facility_code = Column(String(30), unique=True, nullable=False, index=True)
    facility_name = Column(String(255), nullable=False)

    # ROOM | LAB | AUDITORIUM | GYMNASIUM | FIELD | OTHER
    facility_type = Column(String(30), nullable=False, default="ROOM")
    building      = Column(String(100), nullable=True)
    capacity      = Column(Integer, nullable=True)
    description   = Column(String(500), nullable=True)
    is_bookable   = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FacilityBooking(Base):
    __tablename__ = "facility_bookings"

    id                   = Column(Integer, primary_key=True, index=True)
    facility_id          = Column(Integer, ForeignKey("facilities.id"), index=True, nullable=False)
    requestor_account_id = Column(Integer, ForeignKey("user_accounts.account_id"), index=True, nullable=False)
    org_id               = Column(Integer, ForeignKey("student_organizations.id"), nullable=True)

    event_title       = Column(String(255), nullable=False)
    event_description = Column(Text, nullable=True)

    booking_date = Column(Date, nullable=False, index=True)
    time_start   = Column(DateTime(timezone=True), nullable=False)
    time_end     = Column(DateTime(timezone=True), nullable=False)

    attendee_count = Column(Integer, nullable=True)

    # PENDING | APPROVED | REJECTED | CANCELLED
    status = Column(String(20), nullable=False, default="PENDING", index=True)

    secretary_notes            = Column(String(500), nullable=True)
    processed_by_secretary_id  = Column(Integer, ForeignKey("user_accounts.account_id"), nullable=True)
    processed_at               = Column(DateTime(timezone=True), nullable=True)
    rejection_reason           = Column(String(500), nullable=True)
    cancelled_at               = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
