from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, case, func
from src.core.security import require_admin, get_current_user
from . import schemas
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount
from src.modules.enrollment.models import StudentEnrollmentRequest, StudentProfile
from src.modules.audit import service as audit_service

dashboards_router = APIRouter(tags=["Portal Dashboards"])



# ADMIN DASHBOARD

@dashboards_router.get("/admin/stats", response_model=schemas.AdminStatsResponse)
def get_admin_dashboard_statistics(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    if current_user.account_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Only administrators can view these statistics.",
        )

    
    student_count, faculty_count = (
        database_session.query(
            func.sum(case((UserAccount.account_role == "STUDENT", 1), else_=0)),
            func.sum(case((UserAccount.account_role == "FACULTY", 1), else_=0)),
        ).one()
    )

    pending_requests = database_session.query(StudentEnrollmentRequest).filter(
        StudentEnrollmentRequest.review_status == "PENDING"
    ).count()

    return schemas.AdminStatsResponse(
        total_students=int(student_count or 0),
        total_faculty=int(faculty_count or 0),
        pending_enrollment_requests=pending_requests,
    )



# STUDENT DASHBOARD
@dashboards_router.get("/student/profile", response_model=schemas.StudentProfileResponse)
def get_student_dashboard_profile(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):

    profile = database_session.query(StudentProfile).filter(
        StudentProfile.student_account_id == current_user.account_id
    ).first()

    full_name   = "Student"
    student_num = None
    course      = None
    year_level  = 1
    semester    = 1

    if profile:
        full_name   = f"{profile.first_name} {profile.last_name}".strip() or "Student"
        student_num = profile.student_number
        course      = profile.current_course
        year_level  = profile.current_year_level or 1
        semester    = profile.current_semester   or 1

    from src.modules.enrollment.models import StudentEnrollmentRequest
    has_pending = database_session.query(StudentEnrollmentRequest).filter(
        StudentEnrollmentRequest.student_account_id == current_user.account_id,
        StudentEnrollmentRequest.review_status      == "PENDING",
    ).first() is not None

    clearance = (
        {"status": "PENDING",  "details": "Enrollment request awaiting admin review"}
        if has_pending else
        {"status": "CLEARED",  "details": "Ready for next enrollment"}
    )

    account_status = "Active" if current_user.is_active_account else "Locked"

    return schemas.StudentProfileResponse(
        account_id=    current_user.account_id,
        email_address= current_user.email_address,
        account_role=  current_user.account_role,
        account_status=account_status,
        name=          full_name,
        student_id=    student_num,
        course=        course,
        year_level=    year_level,
        semester=      semester,
        clearance=     clearance,
    )

@dashboards_router.get(
    "/student/academic-standing",
    response_model=schemas.AcademicStandingResponse,
)
def get_student_academic_standing(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
   
    if current_user.account_role != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for students only.",
        )

    # Load student profile for year/semester standing
    profile = database_session.query(StudentProfile).filter(
        StudentProfile.student_account_id == current_user.account_id
    ).first()

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found. Contact the registrar.",
        )

    current_year     = profile.current_year_level or 1
    current_semester = profile.current_semester   or 1
    student_name     = f"{profile.first_name} {profile.last_name}".strip()

    # Run the checker
    from src.modules.enrollment.prerequisite_checker import PrerequisiteChecker
    checker  = PrerequisiteChecker(database_session)
    standing = checker.get_academic_standing(
        student_account_id=current_user.account_id,
        current_year=current_year,
        current_semester=current_semester,
    )

    # Convert raw dict grade records to GradeRecord schema
    def to_grade_records(records: list) -> list[schemas.GradeRecord]:
        return [schemas.GradeRecord(**r) for r in records]

    # Safely access a field from either a dataclass/object or a plain dict.
    # PrerequisiteChecker may return a RecommendationResult dataclass or a
    # dict depending on internal code path — this prevents AttributeError.
    def _safe_get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    # Convert RecommendationResult (dataclass or dict) to NextSemesterRecommendation schema
    rec = standing["next_semester_recommendation"]

    raw_subject_results = _safe_get(rec, "subject_results", [])

    next_rec = schemas.NextSemesterRecommendation(
        verdict=_safe_get(rec, "verdict", "UNKNOWN"),
        pass_rate=_safe_get(rec, "pass_rate", 0.0),
        available_count=_safe_get(rec, "available_count", 0),
        blocked_count=_safe_get(rec, "blocked_count", 0),
        pending_count=_safe_get(rec, "pending_count", 0),
        flagged_subjects=_safe_get(rec, "flagged_subjects", []),
        suggested_action=_safe_get(rec, "suggested_action", ""),
        subject_results=[
            schemas.SubjectAvailabilityResult(
                subject_id=_safe_get(r, "subject_id", -1),
                subject_code=_safe_get(r, "subject_code", ""),
                subject_title=_safe_get(r, "subject_title", ""),
                credit_units=_safe_get(r, "credit_units", 0),
                status=_safe_get(r, "status", "UNKNOWN"),
                prereq_code=_safe_get(r, "prereq_code"),
                prereq_title=_safe_get(r, "prereq_title"),
                prereq_status=_safe_get(r, "prereq_status"),
                blocking_reason=_safe_get(r, "blocking_reason"),
            )
            for r in raw_subject_results
        ],
    )

    return schemas.AcademicStandingResponse(
        student_year_level=current_year,
        student_semester=current_semester,
        student_name=student_name,
        current_subjects=to_grade_records(standing["current_subjects"]),
        passed_subjects=to_grade_records(standing["passed_subjects"]),
        next_semester_recommendation=next_rec,
    )



# ADMIN — OMNI SEARCH
@dashboards_router.get("/admin/search", response_model=list[schemas.OmniSearchResult])
def omni_search(
    q: str = Query(min_length=1, max_length=100),
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):

    # ── NATURAL LANGUAGE PARSER ──
    action_verbs = ["manage", "suspend", "activate", "view", "edit", "find", "search", "update"]
    search_query = q.lower().strip()
    
    for verb in action_verbs:
        if search_query.startswith(f"{verb} "):
            search_query = search_query[len(verb)+1:].strip()
            break

    term = f"%{search_query}%"
    results = []

    # Search students by email, name, or student number
    # NOTE: No per-query .limit() — all matches are collected first, then
    # the combined results list is capped at 15 to avoid hiding users with
    # common names that would be silently dropped by a premature limit(5).
    matched_students = (
        database_session.query(UserAccount, StudentProfile)
        .join(StudentProfile, StudentProfile.student_account_id == UserAccount.account_id)
        .filter(UserAccount.account_role == "STUDENT")
        .filter(
            or_(
                UserAccount.email_address.ilike(term),
                StudentProfile.first_name.ilike(term),
                StudentProfile.last_name.ilike(term),
                StudentProfile.student_number.ilike(term),
            )
        )
        .all()
    )
    for user, profile in matched_students:
        full_name = f"{profile.first_name} {profile.last_name}".strip()
        results.append(schemas.OmniSearchResult(
            result_type="STUDENT",
            result_id=user.account_id,
            primary_text=full_name or user.email_address,
            secondary_text=profile.student_number or user.email_address,
        ))

    # Search faculty by name or employee ID
    from src.modules.faculty.models import FacultyProfile
    matched_faculty = (
        database_session.query(FacultyProfile)
        .filter(or_(
            FacultyProfile.first_name.ilike(term),
            FacultyProfile.last_name.ilike(term),
            FacultyProfile.employee_id.ilike(term),
        ))
        .all()
    )
    for fp in matched_faculty:
        results.append(schemas.OmniSearchResult(
            result_type="FACULTY",
            result_id=fp.faculty_account_id,
            primary_text=f"{fp.first_name} {fp.last_name}",
            secondary_text=fp.academic_department,
        ))

    # Search subjects by code or title
    from src.modules.enrollment.models import CurriculumSubject
    matched_subjects = (
        database_session.query(CurriculumSubject)
        .filter(or_(
            CurriculumSubject.subject_code.ilike(term),
            CurriculumSubject.subject_title.ilike(term),
        ))
        .all()
    )
    for subj in matched_subjects:
        results.append(schemas.OmniSearchResult(
            result_type="SUBJECT",
            result_id=subj.subject_id,
            primary_text=subj.subject_code,
            secondary_text=subj.subject_title,
        ))

    return results[:15]



# ADMIN — USER MANAGEMENT
@dashboards_router.get("/admin/users", response_model=list[schemas.UserSearchResult])
def list_all_users(
    role:  str = Query(default="ALL"),
    skip:  int = Query(default=0,   ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    query = database_session.query(UserAccount)
    if role != "ALL":
        query = query.filter(UserAccount.account_role == role)
    return query.order_by(UserAccount.email_address).offset(skip).limit(limit).all()


@dashboards_router.get("/admin/users/search", response_model=list[schemas.UserSearchResult])
def search_user_accounts(
    q: str = Query(min_length=1, max_length=100),
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    term = f"%{q}%"
    return (
        database_session.query(UserAccount)
        .filter(UserAccount.email_address.ilike(term))
        .order_by(UserAccount.email_address)
        .limit(20)
        .all()
    )


@dashboards_router.get(
    "/admin/students/{account_id}/grades",
)
def get_student_grades_for_admin(
    account_id: int,
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):

    from src.modules.faculty import repository as faculty_repo

    student = database_session.query(UserAccount).filter(
        UserAccount.account_id == account_id,
        UserAccount.account_role == "STUDENT",
    ).first()

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No student account found with ID {account_id}.",
        )

    records = faculty_repo.fetch_student_transcript_with_subjects(
        database_session=database_session,
        target_student_id=account_id,
    )

    return {
        "student_account_id": account_id,
        "email_address":      student.email_address,
        "records":            [r.model_dump() for r in records],
    }


@dashboards_router.post("/admin/students/create", status_code=status.HTTP_201_CREATED)
def create_student_direct(
    request: Request,
    student_data: schemas.DirectAdmissionRequest,
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):

    from src.modules.auth import service as auth_service, schemas as auth_schemas

    reg = auth_schemas.RegistrationRequest(
        email_address=student_data.email,
        plain_text_password=student_data.password,
        account_role="STUDENT",
        first_name=student_data.full_name.split()[0] if student_data.full_name else "Student",
        last_name=" ".join(student_data.full_name.split()[1:]) if student_data.full_name else "",
        student_number=student_data.student_number,
        course=student_data.course,
        passkey_code=None,
    )

    result = auth_service.process_user_registration(
        database_session=database_session,
        registration_data=reg,
        ip_address=request.client.host if request.client else None,
        skip_passkey=True,
    )

    audit_service.log_event(
        database_session=database_session,
        event_type="STUDENT_ADMITTED",
        actor_id=_admin.account_id,
        actor_email=_admin.email_address,
        target_type="student",
        target_id=result.account_id,
        ip_address=request.client.host if request.client else None,
        payload={
            "student_number": student_data.student_number,
            "course":         student_data.course,
            "year_level":     student_data.year_level,
            "email":          student_data.email,
        },
    )

    return {
        "message":    f"Student account created for {student_data.email}.",
        "account_id": result.account_id,
    }


@dashboards_router.patch("/admin/users/{account_id}/status")
def update_user_active_status(
    request: Request,
    account_id: int,
    status_data: schemas.UpdateUserStatusRequest,
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    target_user = database_session.query(UserAccount).filter(
        UserAccount.account_id == account_id
    ).first()

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No account found with ID {account_id}.",
        )

    target_user.is_active_account = status_data.is_active
    database_session.commit()

    event_type = "USER_ACTIVATED" if status_data.is_active else "USER_SUSPENDED"
    audit_service.log_event(
        database_session=database_session,
        event_type=event_type,
        actor_id=_admin.account_id,
        actor_email=_admin.email_address,
        target_type="user",
        target_id=account_id,
        ip_address=request.client.host if request.client else None,
        payload={
            "target_email": target_user.email_address,
            "target_role":  target_user.account_role,
            "new_status":   "active" if status_data.is_active else "suspended",
        },
    )

    action = "activated" if status_data.is_active else "deactivated"
    return {"message": f"Account {target_user.email_address} {action} successfully."}