from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from .models import EnrollmentForecast, ForecastAlert
from src.modules.enrollment.models import StudentEnrollmentRequest, CurriculumSubject
from src.modules.faculty.models import FacultyProfile, GradebookEntry


def fetch_all_curriculum_subjects(db: Session) -> list[CurriculumSubject]:
    return (
        db.query(CurriculumSubject)
        .order_by(CurriculumSubject.target_year_level, CurriculumSubject.target_semester)
        .all()
    )


def fetch_enrollment_requests_with_subjects(db: Session) -> list[StudentEnrollmentRequest]:
    return (
        db.query(StudentEnrollmentRequest)
        .filter(StudentEnrollmentRequest.extracted_subjects.isnot(None))
        .all()
    )


def fetch_faculty_capacity(db: Session) -> tuple[int, int]:
    """Returns (total_max_load, total_remaining_load) for available faculty."""
    result = db.query(
        func.coalesce(func.sum(FacultyProfile.maximum_teaching_load), 0),
        func.coalesce(
            func.sum(FacultyProfile.maximum_teaching_load - FacultyProfile.current_teaching_load),
            0,
        ),
    ).filter(FacultyProfile.is_available_for_classes == True).one()
    return int(result[0]), int(result[1])


def fetch_gradebook_counts_per_subject(db: Session) -> dict[int, int]:
    """Returns {curriculum_subject_id: distinct_student_count}."""
    rows = (
        db.query(
            GradebookEntry.curriculum_subject_id,
            func.count(GradebookEntry.student_account_id),
        )
        .filter(GradebookEntry.student_account_id.isnot(None))
        .group_by(GradebookEntry.curriculum_subject_id)
        .all()
    )
    return {row[0]: row[1] for row in rows}


def save_forecasts(db: Session, forecasts: list[EnrollmentForecast]) -> None:
    db.query(EnrollmentForecast).update({"is_current": False})
    for f in forecasts:
        db.add(f)
    db.commit()


def fetch_current_forecasts(db: Session) -> list[EnrollmentForecast]:
    return (
        db.query(EnrollmentForecast)
        .filter(EnrollmentForecast.is_current == True)
        .order_by(
            EnrollmentForecast.target_year_level,
            EnrollmentForecast.target_semester,
            EnrollmentForecast.subject_code,
        )
        .all()
    )


def clear_active_alerts(db: Session) -> None:
    db.query(ForecastAlert).filter(ForecastAlert.is_dismissed == False).delete()
    db.commit()


def save_alert(db: Session, alert: ForecastAlert) -> ForecastAlert:
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def fetch_active_alerts(db: Session) -> list[ForecastAlert]:
    return (
        db.query(ForecastAlert)
        .filter(ForecastAlert.is_dismissed == False)
        .order_by(ForecastAlert.created_at.desc())
        .all()
    )


def fetch_alert_by_id(db: Session, alert_id: int) -> ForecastAlert | None:
    return db.query(ForecastAlert).filter(ForecastAlert.alert_id == alert_id).first()


def dismiss_alert(db: Session, alert: ForecastAlert) -> ForecastAlert:
    alert.is_dismissed = True
    alert.dismissed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert
