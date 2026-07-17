from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from src.core.security import require_admin, get_current_user
from . import schemas, service, repository, search_service
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount
from src.modules.audit import service as audit_service
from src.modules.auth import service as auth_service, schemas as auth_schemas

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
    return service.get_admin_stats(database_session)


# STUDENT DASHBOARD

@dashboards_router.get("/student/profile", response_model=schemas.StudentProfileResponse)
def get_student_dashboard_profile(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.get_student_profile_data(database_session, current_user)


@dashboards_router.get("/student/academic-standing", response_model=schemas.AcademicStandingResponse)
def get_student_academic_standing(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    if current_user.account_role != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for students only.",
        )
    return service.get_academic_standing(database_session, current_user)


# ADMIN — OMNI SEARCH

@dashboards_router.get("/admin/search", response_model=list[schemas.OmniSearchResult])
def omni_search(
    q: str = Query(min_length=1, max_length=100),
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    return search_service.run_omni_search(database_session, q)


# ADMIN — USER MANAGEMENT

@dashboards_router.get("/admin/users", response_model=list[schemas.UserSearchResult])
def list_all_users(
    role:  str = Query(default="ALL"),
    skip:  int = Query(default=0,   ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    return repository.list_users(database_session, role, skip, limit)


@dashboards_router.get("/admin/users/search", response_model=list[schemas.UserSearchResult])
def search_user_accounts(
    q: str = Query(min_length=1, max_length=100),
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    return repository.search_users_by_email(database_session, q)


@dashboards_router.get("/admin/students/{account_id}/grades")
def get_student_grades_for_admin(
    account_id: int,
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    from src.modules.faculty import repository as faculty_repo

    student = repository.get_student_by_id(database_session, account_id)
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
    reg = auth_schemas.RegistrationRequest(
        email_address=      student_data.email,
        plain_text_password=student_data.password,
        account_role=       "STUDENT",
        first_name=         student_data.full_name.split()[0] if student_data.full_name else "Student",
        last_name=          " ".join(student_data.full_name.split()[1:]) if student_data.full_name else "",
        student_number=     student_data.student_number,
        course=             student_data.course,
        passkey_code=       None,
    )
    result = auth_service.process_user_registration(
        database_session=database_session,
        registration_data=reg,
        ip_address=request.client.host if request.client else None,
        skip_passkey=True,
    )
    audit_service.log_event(
        database_session=database_session,
        event_type=  "STUDENT_ADMITTED",
        actor_id=    _admin.account_id,
        actor_email= _admin.email_address,
        target_type= "student",
        target_id=   result.account_id,
        ip_address=  request.client.host if request.client else None,
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
    target_user = repository.set_user_active_status(database_session, account_id, status_data.is_active)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No account found with ID {account_id}.",
        )

    event_type = "USER_ACTIVATED" if status_data.is_active else "USER_SUSPENDED"
    audit_service.log_event(
        database_session=database_session,
        event_type=  event_type,
        actor_id=    _admin.account_id,
        actor_email= _admin.email_address,
        target_type= "user",
        target_id=   account_id,
        ip_address=  request.client.host if request.client else None,
        payload={
            "target_email": target_user.email_address,
            "target_role":  target_user.account_role,
            "new_status":   "active" if status_data.is_active else "suspended",
        },
    )
    action = "activated" if status_data.is_active else "deactivated"
    return {"message": f"Account {target_user.email_address} {action} successfully."}


# STUDENT SCHEDULE

@dashboards_router.get("/student/schedule")
def get_student_schedule(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    if current_user.account_role != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for students only.",
        )
    return service.get_student_schedule(database_session, current_user.account_id)


# SE-04: Student at-risk self-assessment

@dashboards_router.get("/student/at-risk")
def get_student_at_risk_assessment(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    if current_user.account_role != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for students only.",
        )
    from src.modules.enrollment.at_risk_engine import assess_student_risk
    result = assess_student_risk(database_session, current_user.account_id)
    return {
        "student_account_id":   result.student_account_id,
        "risk_score":           result.risk_score,
        "risk_level":           result.risk_level,
        "breakdown": {
            "failed_load_score":  result.breakdown.failed_load_score,
            "gwa_score":          result.breakdown.gwa_score,
            "variance_score":     result.breakdown.variance_score,
            "consultation_score": result.breakdown.consultation_score,
        },
        "interventions":        result.interventions,
        "gwa":                  result.gwa,
        "failed_major_count":   result.failed_major_count,
        "failed_minor_count":   result.failed_minor_count,
        "has_any_consultation": result.has_any_consultation,
    }


# SE-04: Admin at-risk students list

@dashboards_router.get("/admin/at-risk-students")
def get_admin_at_risk_students(
    min_score: int = Query(default=40, ge=0, le=100),
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    return service.get_at_risk_students(database_session, min_score)


# STUDENT ENROLLMENT STATUS

@dashboards_router.get("/student/enrollment-status")
def get_student_enrollment_status(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    if current_user.account_role != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for students only.",
        )
    return service.get_student_enrollment_history(database_session, current_user.account_id)
