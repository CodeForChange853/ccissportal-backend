from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from typing import List

from src.core.security import get_current_user, require_admin, require_faculty
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount

from . import schemas, service, repository

faculty_router = APIRouter(
    tags=["Faculty & Grades Management"],
)


# ADMIN ROUTES

@faculty_router.post("/admin/faculty/bulk-assign")
def bulk_assign_classes_to_professor(
    request: Request,
    assignment_data: schemas.BulkFacultyAssignmentRequest,
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
 
    updated_profile = service.bulk_assign_faculty_load(
        database_session=database_session,
        assignment_data=assignment_data,
        actor_id=admin.account_id,
        actor_email=admin.email_address,
        ip_address=request.client.host if request.client else None,
    )
    return {
        "message": "Subjects successfully assigned.",
        "new_load": updated_profile.current_teaching_load,
    }


@faculty_router.post("/admin/faculty/assign")
def assign_class_to_professor(
    request: Request,
    assignment_data: schemas.FacultyAssignmentRequest,
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
    # Existing logic remains exactly as is
    updated_profile = service.evaluate_and_assign_faculty_load(
        database_session=database_session,
        assignment_data=assignment_data,
        actor_id=admin.account_id,
        actor_email=admin.email_address,
        ip_address=request.client.host if request.client else None,
    )
    return {
        "message": "Professor successfully assigned.",
        "new_load": updated_profile.current_teaching_load,
    }


@faculty_router.get("/admin/faculty", response_model=List[schemas.AdminFacultyListItem])
def list_all_faculty(
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
 
    return repository.fetch_all_faculty_for_admin(
        database_session=database_session
    )


# FACULTY ROUTES


@faculty_router.get("/faculty/load", response_model=List[schemas.FacultySubjectLoad])
def get_my_teaching_load(
    database_session: Session = Depends(get_database_session),
    current_faculty: UserAccount = Depends(require_faculty),
):
   
    return repository.fetch_faculty_subjects(
        database_session=database_session,
        faculty_account_id=current_faculty.account_id,
    )


@faculty_router.put("/faculty/grades/update")
def submit_student_grade_update(
    request: Request,                                         
    grade_data: schemas.GradeSubmissionRequest,
    database_session: Session = Depends(get_database_session),
    current_faculty: UserAccount = Depends(require_faculty),
):
  
    service.securely_update_student_grade(
        database_session=database_session,
        faculty_account_id=current_faculty.account_id,
        grade_data=grade_data,
        actor_email=current_faculty.email_address,           
        ip_address=request.client.host if request.client else None, 
    )
    return {"message": "Grade successfully updated."}

@faculty_router.get("/faculty/class/{subject_code}", response_model=List[schemas.ClassRosterResponse])
def get_class_roster(
    subject_code: str,
    database_session: Session = Depends(get_database_session),
    current_faculty: UserAccount = Depends(require_faculty),
):
    return service.fetch_class_roster(
        database_session=database_session,
        faculty_account_id=current_faculty.account_id,
        subject_code=subject_code
    )

@faculty_router.post("/faculty/sync-grades")
def batch_sync_grades(
    request: Request,
    sync_data: schemas.SyncGradesRequest,
    database_session: Session = Depends(get_database_session),
    current_faculty: UserAccount = Depends(require_faculty),
):
    sync_result = service.sync_offline_grades(
        database_session=database_session,
        faculty_account_id=current_faculty.account_id,
        sync_data=sync_data,
        actor_email=current_faculty.email_address,
        ip_address=request.client.host if request.client else None
    )
    return {
        "status": "SUCCESS",
        "synced_records": sync_result["synced_count"],
        "skipped_count": sync_result["skipped_count"],
        "skipped_keys": sync_result["skipped_keys"],
    }


# STUDENT ROUTES
@faculty_router.get("/student/my-grades", response_model=List[schemas.StudentGradeReport])
def view_my_student_transcript(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
   
    return repository.fetch_student_transcript_with_subjects(
        database_session=database_session,
        target_student_id=current_user.account_id,
    )