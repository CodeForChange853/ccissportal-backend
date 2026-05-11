# backend-v2/src/modules/faculty/repository.py


from sqlalchemy.orm import Session
from sqlalchemy import distinct
from .models import FacultyProfile, GradebookEntry
from src.modules.enrollment.models import CurriculumSubject
from . import schemas


def fetch_faculty_profile_by_account(
    database_session: Session, target_account_id: int
) -> FacultyProfile | None:
  
    return database_session.query(FacultyProfile).filter(
        FacultyProfile.faculty_account_id == target_account_id
    ).first()


def fetch_specific_grade_record(
    database_session: Session,
    student_id: int,
    faculty_id: int,
    subject_id: int
) -> GradebookEntry | None:
  
    return database_session.query(GradebookEntry).filter(
        GradebookEntry.student_account_id == student_id,
        GradebookEntry.faculty_account_id == faculty_id,
        GradebookEntry.curriculum_subject_id == subject_id
    ).first()


def fetch_faculty_subjects(
    database_session: Session,
    faculty_account_id: int
) -> list[schemas.FacultySubjectLoad]:

    rows = (
        database_session.query(CurriculumSubject)
        .join(
            GradebookEntry,
            GradebookEntry.curriculum_subject_id == CurriculumSubject.subject_id
        )
        .filter(GradebookEntry.faculty_account_id == faculty_account_id)
        .order_by(CurriculumSubject.subject_id)
        .all()
    )

    
    seen = set()
    unique_rows = []
    for subject in rows:
        if subject.subject_id not in seen:
            seen.add(subject.subject_id)
            unique_rows.append(subject)
    rows = unique_rows

    return [
        schemas.FacultySubjectLoad(
            code=subject.subject_code,
            title=subject.subject_title,
            units=subject.credit_units,
            
            schedule="TBA",
            room="TBA",
            section="Regular",
        )
        for subject in rows
    ]


def fetch_student_transcript_with_subjects(
    database_session: Session,
    target_student_id: int
) -> list[schemas.StudentGradeReport]:
    rows = (
        database_session.query(GradebookEntry, CurriculumSubject)
        .join(
            CurriculumSubject,
            GradebookEntry.curriculum_subject_id == CurriculumSubject.subject_id
        )
        .filter(GradebookEntry.student_account_id == target_student_id)
        .all()
    )

    return [
    schemas.StudentGradeReport(
        subject_code=     subject.subject_code,
        subject_title=    subject.subject_title,
        credit_units=     subject.credit_units,   # Fix: was missing, caused wrong GWA
        target_year_level=subject.target_year_level,
        target_semester=  subject.target_semester,
        midterm_grade=    grade.midterm_grade,
        system_grade=     grade.system_grade,
        final_grade=      grade.final_grade,
        completion_status=grade.completion_status,
    )
    for grade, subject in rows
]

def fetch_all_faculty_for_admin(
    database_session: Session,
) -> list:

    from src.modules.auth.models import UserAccount

    rows = (
        database_session.query(FacultyProfile, UserAccount)
        .join(UserAccount, UserAccount.account_id == FacultyProfile.faculty_account_id)
        .filter(UserAccount.account_role == "FACULTY")
        .order_by(FacultyProfile.academic_department, FacultyProfile.last_name)
        .all()
    )

    # Return plain dicts — the router builds the response model from these
    result = []
    for profile, account in rows:
        result.append({
            "account_id":               account.account_id,
            "email_address":            account.email_address,
            "first_name":               profile.first_name,
            "last_name":                profile.last_name,
            "employee_id":              profile.employee_id,
            "academic_department":      profile.academic_department,
            "current_teaching_load":    profile.current_teaching_load,
            "maximum_teaching_load":    profile.maximum_teaching_load,
            "is_available_for_classes": profile.is_available_for_classes,
        })
    return result

def fetch_class_roster_by_subject(
    database_session: Session,
    faculty_account_id: int,
    subject_code: str
) -> list[schemas.ClassRosterResponse]:
    from src.modules.auth.models import UserAccount
    from src.modules.enrollment.models import StudentProfile

    rows = (
        database_session.query(GradebookEntry, CurriculumSubject, UserAccount, StudentProfile)
        .join(CurriculumSubject, GradebookEntry.curriculum_subject_id == CurriculumSubject.subject_id)
        .outerjoin(UserAccount, GradebookEntry.student_account_id == UserAccount.account_id)
        .outerjoin(StudentProfile, UserAccount.account_id == StudentProfile.student_account_id)
        .filter(
            GradebookEntry.faculty_account_id == faculty_account_id,
            CurriculumSubject.subject_code == subject_code,
            GradebookEntry.student_account_id != None
        )
        .all()
    )

    roster = []
    for grade, subject, account, profile in rows:
        name = f"{profile.first_name} {profile.last_name}" if profile else "Unknown Student"
        student_id_str = profile.student_number if profile and profile.student_number else str(account.account_id)

        roster.append(
            schemas.ClassRosterResponse(
                student_account_id=account.account_id,
                curriculum_subject_id=subject.subject_id,
                student_id=student_id_str,
                student_name=name,
                midterm_grade=grade.midterm_grade,
                system_grade=grade.system_grade,
                final_grade=grade.final_grade,
                override_reason=grade.override_reason,
                status=grade.completion_status
            )
        )
    return roster