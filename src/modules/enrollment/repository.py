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


def fetch_prereq_graph_data(database_session: Session) -> dict:
    subjects = fetch_all_curriculum_subjects(database_session)
    nodes = [
        {
            "id":    s.subject_id,
            "code":  s.subject_code,
            "title": s.subject_title,
            "year":  s.target_year_level,
            "sem":   s.target_semester,
            "units": s.credit_units,
            "course": s.course,
        }
        for s in subjects
    ]
    edges = [
        {"source": s.prerequisite_subject_id, "target": s.subject_id}
        for s in subjects
        if s.prerequisite_subject_id is not None
    ]
    return {"nodes": nodes, "edges": edges}


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
    limit: int | None = 100,
    status_filter: str | None = None,
) -> list[StudentEnrollmentRequest]:
   
    query = database_session.query(StudentEnrollmentRequest)

    if status_filter:
        query = query.filter(StudentEnrollmentRequest.review_status == status_filter)

    query = query.order_by(StudentEnrollmentRequest.date_submitted.asc()).offset(skip)

    if limit is not None:
        query = query.limit(limit)

    return query.all()


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


# ── Admin: Student Records (read-only roster) ─────────────────────────────────

def fetch_student_records(
    database_session: Session,
    search: str | None = None,
    course: str | None = None,
    year_level: int | None = None,
    skip: int = 0,
    limit: int | None = 200,
) -> list:
    from sqlalchemy import func as _func
    from .models import StudentProfile

    latest_req_subq = (
        database_session.query(
            StudentEnrollmentRequest.student_account_id,
            _func.max(StudentEnrollmentRequest.request_id).label("latest_request_id"),
        )
        .group_by(StudentEnrollmentRequest.student_account_id)
        .subquery()
    )

    query = (
        database_session.query(
            StudentProfile,
            StudentEnrollmentRequest.review_status,
            StudentEnrollmentRequest.cor_release_status,
        )
        .outerjoin(
            latest_req_subq,
            StudentProfile.student_account_id == latest_req_subq.c.student_account_id,
        )
        .outerjoin(
            StudentEnrollmentRequest,
            StudentEnrollmentRequest.request_id == latest_req_subq.c.latest_request_id,
        )
    )

    if search:
        like = f"%{search}%"
        query = query.filter(
            (StudentProfile.first_name.ilike(like))
            | (StudentProfile.last_name.ilike(like))
            | (StudentProfile.student_number.ilike(like))
        )
    if course:
        query = query.filter(StudentProfile.current_course == course)
    if year_level is not None:
        query = query.filter(StudentProfile.current_year_level == year_level)

    query = query.order_by(StudentProfile.last_name, StudentProfile.first_name).offset(skip)

    if limit is not None:
        query = query.limit(limit)

    return query.all()