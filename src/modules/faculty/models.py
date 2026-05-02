# backend-v2/src/modules/faculty/models.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, Index
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