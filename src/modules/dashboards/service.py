from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Any
from src.modules.auth.models import UserAccount
from . import repository, schemas


def get_admin_stats(db: Session) -> schemas.AdminStatsResponse:
    student_count, faculty_count = repository.get_role_counts(db)
    return schemas.AdminStatsResponse(
        total_students=student_count,
        total_faculty=faculty_count,
        pending_enrollment_requests=repository.get_pending_enrollment_count(db),
    )


def get_student_profile_data(db: Session, current_user: UserAccount) -> schemas.StudentProfileResponse:
    profile = repository.get_student_profile(db, current_user.account_id)

    full_name = "Student"
    student_num = None
    course = None
    year_level = 1
    semester = 1

    if profile:
        full_name   = f"{profile.first_name} {profile.last_name}".strip() or "Student"
        student_num = profile.student_number
        course      = profile.current_course
        year_level  = profile.current_year_level or 1
        semester    = profile.current_semester   or 1

    has_pending = repository.has_pending_enrollment(db, current_user.account_id)
    clearance = (
        {"status": "PENDING",  "details": "Enrollment request awaiting admin review"}
        if has_pending else
        {"status": "CLEARED",  "details": "Ready for next enrollment"}
    )

    return schemas.StudentProfileResponse(
        account_id=    current_user.account_id,
        email_address= current_user.email_address,
        account_role=  current_user.account_role,
        account_status="Active" if current_user.is_active_account else "Locked",
        name=          full_name,
        student_id=    student_num,
        course=        course,
        year_level=    year_level,
        semester=      semester,
        clearance=     clearance,
        was_reformed=  current_user.removed_from_wall_at is not None,
    )


def get_academic_standing(
    db: Session, current_user: UserAccount
) -> schemas.AcademicStandingResponse:
    profile = repository.get_student_profile(db, current_user.account_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found. Contact the registrar.",
        )

    current_year     = profile.current_year_level or 1
    current_semester = profile.current_semester   or 1
    student_name     = f"{profile.first_name} {profile.last_name}".strip()

    from src.modules.enrollment.prerequisite_checker import PrerequisiteChecker
    checker  = PrerequisiteChecker(db)
    standing = checker.get_academic_standing(
        student_account_id=current_user.account_id,
        current_year=current_year,
        current_semester=current_semester,
    )

    def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def to_grade_records(records: list[Any]) -> list[schemas.GradeRecord]:
        return [schemas.GradeRecord(**r) for r in records]

    def to_back_subject_records(records: list[Any]) -> list[schemas.BackSubjectRecord]:
        result = []
        for r in records:
            def _g(key: str, default: Any = None, _r: Any = r) -> Any:
                return _r.get(key, default) if isinstance(_r, dict) else getattr(_r, key, default)
            result.append(schemas.BackSubjectRecord(
                subject_id=      _g("subject_id", -1),
                subject_code=    _g("subject_code", ""),
                subject_title=   _g("subject_title", ""),
                credit_units=    _g("credit_units", 0),
                subject_type=    _g("subject_type", "MINOR"),
                times_failed=    _g("times_failed", 1),
                blocking_reason= _g("blocking_reason"),
            ))
        return result

    rec = standing["next_semester_recommendation"]
    raw_subject_results = _safe_get(rec, "subject_results", [])

    next_rec = schemas.NextSemesterRecommendation(
        verdict=         _safe_get(rec, "verdict", "UNKNOWN"),
        pass_rate=       _safe_get(rec, "pass_rate", 0.0),
        available_count= _safe_get(rec, "available_count", 0),
        blocked_count=   _safe_get(rec, "blocked_count", 0),
        pending_count=   _safe_get(rec, "pending_count", 0),
        flagged_subjects=_safe_get(rec, "flagged_subjects", []),
        suggested_action=_safe_get(rec, "suggested_action", ""),
        subject_results=[
            schemas.SubjectAvailabilityResult(
                subject_id=      _safe_get(r, "subject_id", -1),
                subject_code=    _safe_get(r, "subject_code", ""),
                subject_title=   _safe_get(r, "subject_title", ""),
                credit_units=    _safe_get(r, "credit_units", 0),
                status=          _safe_get(r, "status", "UNKNOWN"),
                prereq_code=     _safe_get(r, "prereq_code"),
                prereq_title=    _safe_get(r, "prereq_title"),
                prereq_status=   _safe_get(r, "prereq_status"),
                blocking_reason= _safe_get(r, "blocking_reason"),
                priority_score=  _safe_get(r, "priority_score"),
            )
            for r in raw_subject_results
        ],
    )

    raw_retention = standing.get("retention_status")
    retention_schema = None
    if raw_retention is not None:
        def _gr(key: str, default: Any = None) -> Any:
            return raw_retention.get(key, default) if isinstance(raw_retention, dict) else getattr(raw_retention, key, default)
        retention_schema = schemas.RetentionStatus(
            status=              _gr("status", "GOOD"),
            message=             _gr("message", ""),
            at_risk_major_count= _gr("at_risk_major_count", 0),
            failed_units=        _gr("failed_units", 0),
        )

    return schemas.AcademicStandingResponse(
        student_year_level=          current_year,
        student_semester=            current_semester,
        student_name=                student_name,
        is_irregular=                standing.get("is_irregular", False),
        current_subjects=            to_grade_records(standing["current_subjects"]),
        passed_subjects=             to_grade_records(standing["passed_subjects"]),
        next_semester_recommendation=next_rec,
        back_subjects=               to_back_subject_records(standing.get("back_subjects", [])),
        retention_status=            retention_schema,
    )


def get_student_schedule(db: Session, account_id: int) -> list[dict]:
    rows = repository.get_student_schedule_rows(db, account_id)
    schedule = []
    for entry, subject, faculty in rows:
        instructor_name = (
            f"{faculty.first_name} {faculty.last_name}".strip() if faculty else "TBA"
        )
        schedule.append({
            "code":       subject.subject_code,
            "title":      subject.subject_title,
            "units":      subject.credit_units,
            "time":       "TBA",
            "room":       "TBA",
            "instructor": instructor_name,
        })
    return schedule


def get_at_risk_students(db: Session, min_score: int) -> list[dict]:
    from src.modules.enrollment.at_risk_engine import assess_student_risk

    students = repository.get_active_students_with_profiles(db)
    results = []
    for student, profile in students:
        try:
            assessment = assess_student_risk(db, student.account_id)
        except Exception:
            continue

        if assessment.risk_score < min_score:
            continue

        full_name = (
            f"{profile.first_name} {profile.last_name}".strip()
            if profile else student.email_address
        )
        results.append({
            "student_account_id": student.account_id,
            "student_name":       full_name,
            "student_number":     profile.student_number if profile else None,
            "email_address":      student.email_address,
            "risk_score":         assessment.risk_score,
            "risk_level":         assessment.risk_level,
            "top_intervention":   assessment.interventions[0] if assessment.interventions else None,
            "failed_major_count": assessment.failed_major_count,
            "gwa":                assessment.gwa,
        })

    results.sort(key=lambda r: r["risk_score"], reverse=True)
    return results


def get_student_enrollment_history(db: Session, account_id: int) -> list[dict]:
    requests = repository.get_student_enrollment_history(db, account_id)
    return [
        {
            "request_id":         req.request_id,
            "target_year_level":  req.target_year_level,
            "target_semester":    req.target_semester,
            "review_status":      req.review_status,
            "admin_review_notes": req.admin_review_notes,
            "date_submitted":     req.date_submitted.isoformat() if req.date_submitted else None,
        }
        for req in requests
    ]
