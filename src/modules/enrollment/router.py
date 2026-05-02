# backend-v2/src/modules/enrollment/router.py

from fastapi import APIRouter, Depends, Request, status, Query
from sqlalchemy.orm import Session
from typing import List

from src.core.security import get_current_user, require_admin
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount
from src.modules.enrollment.models import StudentProfile

from . import schemas, service, repository
from src.modules.dashboards.schemas import EnrollmentQueueItem

enrollment_router = APIRouter(
    prefix="/enrollment",
    tags=["Student Enrollment & Admin Approvals"],
)


# STUDENT ROUTES

@enrollment_router.post("/submit", status_code=201)
def submit_new_enrollment(
    request: Request,
    submission_data: schemas.StudentEnrollmentSubmission,
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):

    saved_record = service.process_student_enrollment_submission(
        database_session=database_session,
        student_id=current_user.account_id,
        submission_data=submission_data,
        actor_email=current_user.email_address,
        ip_address=request.client.host if request.client else None,
    )
    return {"request_id": saved_record.request_id, "review_status": saved_record.review_status}


# ADMIN ROUTES
@enrollment_router.get("/pending", response_model=List[EnrollmentQueueItem])
def view_pending_enrollments(
    skip:          int = Query(default=0,     ge=0,         description="Records to skip"),
    limit:         int = Query(default=100,   ge=1, le=200, description="Max records (1–200)"),
    status_filter: str = Query(default="ALL",               description="PENDING | APPROVED | REJECTED | ALL"),
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
    resolved_filter = None if status_filter == "ALL" else status_filter

    requests_list = repository.fetch_pending_requests_for_admins(
        database_session, skip=skip, limit=limit, status_filter=resolved_filter
    )

    if not requests_list:
        return []

    # Single bulk fetch for all student profiles — eliminates N+1
    student_ids = [r.student_account_id for r in requests_list]
    profiles    = database_session.query(StudentProfile).filter(
        StudentProfile.student_account_id.in_(student_ids)
    ).all()
    profile_map = {p.student_account_id: p for p in profiles}

    enriched = []
    for req in requests_list:
        profile        = profile_map.get(req.student_account_id)
        full_name      = f"{profile.first_name} {profile.last_name}".strip() if profile else None
        student_number = profile.student_number if profile else None

        enriched.append(EnrollmentQueueItem(
            request_id=                  req.request_id,
            student_account_id=          req.student_account_id,
            student_name=                full_name,
            student_number=              student_number,
            target_year_level=           req.target_year_level,
            target_semester=             req.target_semester,
            review_status=               req.review_status,
            admin_review_notes=          req.admin_review_notes,
            date_submitted=              req.date_submitted,
            document_verification_token= req.document_verification_token,
            extracted_subjects=          req.extracted_subjects,
            verification_result=         req.verification_result,
            ai_recommendation=           req.ai_recommendation,
        ))

    return enriched


@enrollment_router.post("/{request_id}/decide")
def process_admin_decision(
    request: Request,
    request_id: int,
    decision_data: schemas.AdminApprovalDecision,
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
    updated_record = service.process_admin_enrollment_decision(
        database_session=database_session,
        target_request_id=request_id,
        decision_data=decision_data,
        actor_id=admin.account_id,
        actor_email=admin.email_address,
        ip_address=request.client.host if request.client else None,
    )
    return {"message": f"Request {request_id} marked as {updated_record.review_status}"}

@enrollment_router.post("/bulk-decide")
def submit_bulk_enrollment_decision(
    request: Request,
    decision_data: schemas.BulkAdminApprovalDecision,
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
    processed_count = service.bulk_process_enrollment_decision(
        database_session=database_session,
        decision_data=decision_data,
        actor_id=admin.account_id,
        actor_email=admin.email_address,
        ip_address=request.client.host if request.client else None,
    )
    return {"message": f"Successfully processed {processed_count} enrollments."}

@enrollment_router.get("/curriculum", response_model=List[schemas.SubjectResponse])
def list_all_curriculum_subjects(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return repository.fetch_all_curriculum_subjects(database_session)


@enrollment_router.post("/curriculum/add", response_model=schemas.SubjectResponse)
def create_curriculum_subject(
    subject_data: schemas.CurriculumSubjectCreateRequest,
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
    return service.add_new_subject_to_curriculum(
        database_session=database_session,
        subject_data=subject_data,
    )


@enrollment_router.delete("/curriculum/{subject_id}/remove")
def delete_curriculum_subject(
    subject_id: int,
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
    service.remove_subject_from_curriculum(
        database_session=database_session,
        target_subject_id=subject_id,
    )
    return {"message": "Subject successfully removed from the curriculum."}

@enrollment_router.patch("/curriculum/{subject_id}/update", response_model=schemas.SubjectResponse)
def modify_curriculum_subject(
    subject_id: int,
    update_data: schemas.CurriculumSubjectUpdateRequest,
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
    return service.update_curriculum_subject(
        database_session=database_session,
        target_subject_id=subject_id,
        update_data=update_data,
    )