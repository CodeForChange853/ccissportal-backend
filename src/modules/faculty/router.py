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


# ── TRIAGE ALERTS ──

@faculty_router.get("/faculty/triage-alerts", response_model=List[schemas.TriageAlertOut])
def get_triage_alerts(
    database_session: Session = Depends(get_database_session),
    current_faculty: UserAccount = Depends(require_faculty),
):
    return service.fetch_triage_alerts(
        database_session=database_session,
        faculty_account_id=current_faculty.account_id,
    )


# ── CONSULTATION SLOTS ──

@faculty_router.get("/faculty/consultations/slots", response_model=List[schemas.ConsultationSlotOut])
def list_my_consultation_slots(
    database_session: Session = Depends(get_database_session),
    current_faculty: UserAccount = Depends(require_faculty),
):
    return service.get_consultation_slots(
        database_session=database_session,
        faculty_account_id=current_faculty.account_id,
    )


@faculty_router.post("/faculty/consultations/slots", response_model=schemas.ConsultationSlotOut)
def add_consultation_slot(
    slot_data: schemas.ConsultationSlotCreate,
    database_session: Session = Depends(get_database_session),
    current_faculty: UserAccount = Depends(require_faculty),
):
    return service.create_consultation_slot(
        database_session=database_session,
        faculty_account_id=current_faculty.account_id,
        slot_data=slot_data,
    )


@faculty_router.delete("/faculty/consultations/slots/{slot_id}")
def remove_consultation_slot(
    slot_id: int,
    database_session: Session = Depends(get_database_session),
    current_faculty: UserAccount = Depends(require_faculty),
):
    service.delete_consultation_slot(
        database_session=database_session,
        faculty_account_id=current_faculty.account_id,
        slot_id=slot_id,
    )
    return {"message": "Slot deleted."}

@faculty_router.put("/faculty/consultations/slots/{slot_id}", response_model=schemas.ConsultationSlotOut)
def update_consultation_slot(
    slot_id: int,
    slot_data: schemas.ConsultationSlotUpdate,
    database_session: Session = Depends(get_database_session),
    current_faculty: UserAccount = Depends(require_faculty),
):
    return service.update_consultation_slot(
        database_session=database_session,
        faculty_account_id=current_faculty.account_id,
        slot_id=slot_id,
        slot_data=slot_data,
    )


# ── CONSULTATION REQUESTS ──

@faculty_router.get("/faculty/consultations/requests", response_model=List[schemas.ConsultationRequestOut])
def list_consultation_requests(
    database_session: Session = Depends(get_database_session),
    current_faculty: UserAccount = Depends(require_faculty),
):
    return service.get_consultation_requests(
        database_session=database_session,
        faculty_account_id=current_faculty.account_id,
    )


@faculty_router.put("/faculty/consultations/requests/{request_id}/status")
def update_request_status(
    request_id: int,
    body: schemas.ConsultationStatusUpdate,
    database_session: Session = Depends(get_database_session),
    current_faculty: UserAccount = Depends(require_faculty),
):
    service.update_consultation_request_status(
        database_session=database_session,
        faculty_account_id=current_faculty.account_id,
        request_id=request_id,
        new_status=body.status,
    )
    return {"message": f"Request {request_id} marked as {body.status}."}


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

@faculty_router.get("/student/consultations/faculty", response_model=List[schemas.FacultyWithSlotsOut])
def get_available_faculty(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.get_faculty_for_consultation(database_session=database_session)

@faculty_router.get("/student/consultations/faculty/{faculty_id}/available-slots", response_model=List[schemas.AvailableTimeChunk])
def get_faculty_time_chunks(
    faculty_id: int,
    target_date: str,
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.generate_available_30min_chunks(
        database_session=database_session,
        faculty_account_id=faculty_id,
        target_date=target_date
    )

@faculty_router.post("/student/consultations/requests", response_model=schemas.ConsultationRequestOut)
def submit_student_consultation_booking(
    booking_data: schemas.StudentConsultationBookingCreate,
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.create_student_consultation_request(
        database_session=database_session,
        student_account_id=current_user.account_id,
        booking_data=booking_data
    )

@faculty_router.get("/student/consultations/requests", response_model=List[schemas.ConsultationRequestOut])
def list_my_consultation_bookings(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.get_student_consultation_requests(
        database_session=database_session,
        student_account_id=current_user.account_id
    )