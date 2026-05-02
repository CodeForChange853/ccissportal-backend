# backend-v2/src/modules/enrollment/repository.py

from sqlalchemy.orm import Session
from .models import CurriculumSubject, StudentEnrollmentRequest


def fetch_subjects_by_term(
    database_session: Session, year_level: int, semester: int
) -> list[CurriculumSubject]:
    return database_session.query(CurriculumSubject).filter(
        CurriculumSubject.target_year_level == year_level,
        CurriculumSubject.target_semester   == semester,
    ).all()


def fetch_all_curriculum_subjects(database_session: Session) -> list[CurriculumSubject]:
    return database_session.query(CurriculumSubject).order_by(
        CurriculumSubject.target_year_level,
        CurriculumSubject.target_semester,
        CurriculumSubject.subject_code,
    ).all()


def save_new_enrollment_request(
    database_session: Session, new_request: StudentEnrollmentRequest
) -> StudentEnrollmentRequest:
    database_session.add(new_request)
    database_session.commit()
    database_session.refresh(new_request)
    return new_request


def fetch_pending_requests_for_admins(
    database_session: Session,
    skip: int = 0,
    limit: int = 100,
    status_filter: str | None = None,
) -> list[StudentEnrollmentRequest]:
   
    query = database_session.query(StudentEnrollmentRequest)

    if status_filter:
        query = query.filter(StudentEnrollmentRequest.review_status == status_filter)

    return (
        query
        .order_by(StudentEnrollmentRequest.date_submitted.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def fetch_enrollment_request_by_id(
    database_session: Session, request_id: int
) -> StudentEnrollmentRequest | None:
    return database_session.query(StudentEnrollmentRequest).filter(
        StudentEnrollmentRequest.request_id == request_id
    ).first()


def fetch_subject_by_id(
    database_session: Session, subject_id: int
) -> CurriculumSubject | None:
    return database_session.query(CurriculumSubject).filter(
        CurriculumSubject.subject_id == subject_id
    ).first()


def fetch_subject_by_code(
    database_session: Session, target_code: str
) -> CurriculumSubject | None:
    return database_session.query(CurriculumSubject).filter(
        CurriculumSubject.subject_code == target_code
    ).first()


def save_new_curriculum_subject(
    database_session: Session, new_subject: CurriculumSubject
) -> CurriculumSubject:
    database_session.add(new_subject)
    database_session.commit()
    database_session.refresh(new_subject)
    return new_subject


def delete_subject_record(
    database_session: Session, subject_record: CurriculumSubject
):
    database_session.delete(subject_record)
    database_session.commit()


def update_enrollment_status(
    database_session: Session,
    enrollment_request: StudentEnrollmentRequest,
    new_status: str,
    admin_notes: str | None = None,
) -> StudentEnrollmentRequest:
    enrollment_request.review_status       = new_status
    enrollment_request.admin_review_notes  = admin_notes
    database_session.commit()
    database_session.refresh(enrollment_request)
    return enrollment_request