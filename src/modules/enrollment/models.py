from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from src.core.database_setup import Base


class CurriculumSubject(Base):

    __tablename__ = "curriculum_subjects"

    subject_id = Column(Integer, primary_key=True, index=True)

    subject_code  = Column(String(50),  unique=True, index=True, nullable=False)
    subject_title = Column(String(255), nullable=False)
    credit_units  = Column(Integer,     nullable=False)

    target_year_level = Column(Integer, index=True, nullable=False)
    target_semester   = Column(Integer, index=True, nullable=False)


    prerequisite_subject_id = Column(
        Integer,
        ForeignKey("curriculum_subjects.subject_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


    course = Column(String(20), nullable=False, default="BSCS", server_default="BSCS")


class StudentEnrollmentRequest(Base):

    __tablename__ = "student_enrollment_requests"

    request_id = Column(Integer, primary_key=True, index=True)

    student_account_id = Column(
        Integer, ForeignKey("user_accounts.account_id"), index=True, nullable=False
    )

    target_year_level = Column(Integer, nullable=False)
    target_semester   = Column(Integer, nullable=False)

    document_verification_token = Column(String(255), nullable=True)


    extracted_subjects = Column(JSON, nullable=True)

    verification_result = Column(JSON, nullable=True)

    ai_recommendation = Column(JSON, nullable=True)

    review_status      = Column(String(50), default="PENDING", index=True)
    admin_review_notes = Column(String(500), nullable=True)
    date_submitted     = Column(
        DateTime(timezone=True), server_default=func.now()
    )


class StudentProfile(Base):

    __tablename__ = "student_profiles"

    profile_id = Column(Integer, primary_key=True, index=True)
    student_account_id = Column(
        Integer, ForeignKey("user_accounts.account_id"),
        unique=True, index=True, nullable=False
    )

    first_name     = Column(String(100), nullable=False, index=True)
    last_name      = Column(String(100), nullable=False, index=True)
    student_number = Column(String(50),  unique=True,    index=True)

    current_course      = Column(String(100))
    current_year_level  = Column(Integer, default=1)


    current_semester = Column(Integer, default=1)
    is_ai_verified   = Column(Boolean, default=False, nullable=False)
    is_irregular     = Column(Boolean, default=False, nullable=False)
    security_flags   = Column(JSON, nullable=True) # Tracks reasons for flagging
