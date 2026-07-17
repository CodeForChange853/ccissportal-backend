# backend-v2/src/modules/faculty/models.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, Index, DateTime, Text
from sqlalchemy.sql import func
from src.core.database_setup import Base



class FacultyProfile(Base):

    __tablename__ = "faculty_profiles"

    profile_id          = Column(Integer, primary_key=True, index=True)
    faculty_account_id  = Column(
        Integer, ForeignKey("user_accounts.account_id"),
        unique=True, index=True, nullable=False
    )

    first_name          = Column(String(100), nullable=False, index=True)
    last_name           = Column(String(100), nullable=False, index=True)
    employee_id         = Column(String(50),  unique=True,    index=True)
    academic_department = Column(String(100), nullable=False)

    # Load Balancer counters
    maximum_teaching_load  = Column(Integer, default=4)
    current_teaching_load  = Column(Integer, default=0)
    is_available_for_classes = Column(Boolean, default=True)

    # SE-02 — Intelligent matching fields (added via ALTER TABLE on startup)
    specialization_tags = Column(Text, nullable=True)
    performance_score   = Column(Float, nullable=True, default=0.0)


class GradebookEntry(Base):

    __tablename__ = "gradebook_entries"

    grade_id = Column(Integer, primary_key=True, index=True)

    student_account_id = Column(
        Integer, ForeignKey("user_accounts.account_id"),
        index=True, nullable=True          
    )

    faculty_account_id = Column(
        Integer, ForeignKey("faculty_profiles.faculty_account_id"),
        index=True, nullable=False
    )

    curriculum_subject_id = Column(
        Integer, ForeignKey("curriculum_subjects.subject_id"),
        index=True, nullable=False
    )

    midterm_grade     = Column(Float,     nullable=True)
    system_grade      = Column(Float,     nullable=True)
    final_grade       = Column(Float,     nullable=True)
    raw_scores        = Column(Text,      nullable=True) # JSON string for Quizzes, Exams, Assignments
    override_reason   = Column(String(500), nullable=True)
    completion_status = Column(String(50), default="IN PROGRESS", index=True)


    __table_args__ = (
        Index(
            "ix_gradebook_student_faculty_subject",
            "student_account_id",
            "faculty_account_id",
            "curriculum_subject_id",
        ),
    )


class ConsultationSlot(Base):
    __tablename__ = "consultation_slots"

    slot_id = Column(Integer, primary_key=True, index=True)
    faculty_account_id = Column(
        Integer, ForeignKey("user_accounts.account_id"),
        index=True, nullable=False
    )
    available_date = Column(String(20), nullable=False)   
    start_time  = Column(String(10), nullable=False)  
    end_time    = Column(String(10), nullable=False)   
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class ConsultationRequest(Base):
    __tablename__ = "consultation_requests"

    request_id = Column(Integer, primary_key=True, index=True)
    slot_id = Column(
        Integer, ForeignKey("consultation_slots.slot_id"),
        index=True, nullable=False
    )
    student_account_id = Column(
        Integer, ForeignKey("user_accounts.account_id"),
        index=True, nullable=False
    )
    faculty_account_id = Column(
        Integer, ForeignKey("user_accounts.account_id"),
        index=True, nullable=False
    )
    reason = Column(Text, nullable=False)
    booking_date = Column(String(20), nullable=False)
    start_time = Column(String(10), nullable=False)
    end_time = Column(String(10), nullable=False)
    status = Column(String(20), default="PENDING", index=True)  
    created_at = Column(DateTime(timezone=True), server_default=func.now())