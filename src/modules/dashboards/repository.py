from sqlalchemy.orm import Session
from sqlalchemy import or_, case, func
from src.modules.auth.models import UserAccount
from src.modules.enrollment.models import StudentEnrollmentRequest, StudentProfile, CurriculumSubject
from src.modules.faculty.models import FacultyProfile, GradebookEntry


def get_role_counts(db: Session) -> tuple[int, int]:
    student_count, faculty_count = db.query(
        func.sum(case((UserAccount.account_role == "STUDENT", 1), else_=0)),
        func.sum(case((UserAccount.account_role == "FACULTY", 1), else_=0)),
    ).one()
    return int(student_count or 0), int(faculty_count or 0)


def get_pending_enrollment_count(db: Session) -> int:
    return db.query(StudentEnrollmentRequest).filter(
        StudentEnrollmentRequest.review_status == "PENDING"
    ).count()


def get_student_profile(db: Session, account_id: int) -> StudentProfile | None:
    return db.query(StudentProfile).filter(
        StudentProfile.student_account_id == account_id
    ).first()


def has_pending_enrollment(db: Session, account_id: int) -> bool:
    return db.query(StudentEnrollmentRequest).filter(
        StudentEnrollmentRequest.student_account_id == account_id,
        StudentEnrollmentRequest.review_status == "PENDING",
    ).first() is not None


def search_students(db: Session, term: str) -> list[tuple[UserAccount, StudentProfile]]:
    return (
        db.query(UserAccount, StudentProfile)
        .join(StudentProfile, StudentProfile.student_account_id == UserAccount.account_id)
        .filter(UserAccount.account_role == "STUDENT")
        .filter(or_(
            UserAccount.email_address.ilike(term),
            StudentProfile.first_name.ilike(term),
            StudentProfile.last_name.ilike(term),
            StudentProfile.student_number.ilike(term),
        ))
        .all()
    )


def search_faculty(db: Session, term: str) -> list[FacultyProfile]:
    return (
        db.query(FacultyProfile)
        .filter(or_(
            FacultyProfile.first_name.ilike(term),
            FacultyProfile.last_name.ilike(term),
            FacultyProfile.employee_id.ilike(term),
        ))
        .all()
    )


def search_subjects(db: Session, term: str) -> list[CurriculumSubject]:
    return (
        db.query(CurriculumSubject)
        .filter(or_(
            CurriculumSubject.subject_code.ilike(term),
            CurriculumSubject.subject_title.ilike(term),
        ))
        .all()
    )


def list_users(db: Session, role: str, skip: int, limit: int) -> list[UserAccount]:
    query = db.query(UserAccount)
    if role != "ALL":
        query = query.filter(UserAccount.account_role == role)
    return query.order_by(UserAccount.email_address).offset(skip).limit(limit).all()


def search_users_by_email(db: Session, q: str, limit: int = 20) -> list[UserAccount]:
    return (
        db.query(UserAccount)
        .filter(UserAccount.email_address.ilike(f"%{q}%"))
        .order_by(UserAccount.email_address)
        .limit(limit)
        .all()
    )


def get_user_by_id(db: Session, account_id: int) -> UserAccount | None:
    return db.query(UserAccount).filter(UserAccount.account_id == account_id).first()


def get_student_by_id(db: Session, account_id: int) -> UserAccount | None:
    return db.query(UserAccount).filter(
        UserAccount.account_id == account_id,
        UserAccount.account_role == "STUDENT",
    ).first()


def set_user_active_status(db: Session, account_id: int, is_active: bool) -> UserAccount | None:
    user = get_user_by_id(db, account_id)
    if user is None:
        return None
    user.is_active_account = is_active
    db.commit()
    return user


def get_student_schedule_rows(
    db: Session, account_id: int
) -> list[tuple[GradebookEntry, CurriculumSubject, FacultyProfile]]:
    return (
        db.query(GradebookEntry, CurriculumSubject, FacultyProfile)
        .join(CurriculumSubject, GradebookEntry.curriculum_subject_id == CurriculumSubject.subject_id)
        .outerjoin(FacultyProfile, GradebookEntry.faculty_account_id == FacultyProfile.faculty_account_id)
        .filter(
            GradebookEntry.student_account_id == account_id,
            GradebookEntry.completion_status.in_(["ENROLLED", "IN PROGRESS"]),
        )
        .all()
    )


def get_active_students_with_profiles(db: Session) -> list[tuple[UserAccount, StudentProfile]]:
    return (
        db.query(UserAccount, StudentProfile)
        .outerjoin(StudentProfile, StudentProfile.student_account_id == UserAccount.account_id)
        .filter(UserAccount.account_role == "STUDENT", UserAccount.is_active_account == True)
        .order_by(StudentProfile.last_name)
        .all()
    )


def get_student_enrollment_history(db: Session, account_id: int) -> list[StudentEnrollmentRequest]:
    return (
        db.query(StudentEnrollmentRequest)
        .filter(StudentEnrollmentRequest.student_account_id == account_id)
        .order_by(StudentEnrollmentRequest.date_submitted.desc())
        .all()
    )
