from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import repository, schemas, models
from src.modules.audit import service as audit_service
from src.modules.enrollment.models import CurriculumSubject


def bulk_assign_faculty_load(
    database_session: Session,
    assignment_data: schemas.BulkFacultyAssignmentRequest,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> models.FacultyProfile:

    professor_profile = repository.fetch_faculty_profile_by_account(
        database_session=database_session,
        target_account_id=assignment_data.faculty_account_id
    )

    if professor_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty profile not found."
        )

    if not professor_profile.is_available_for_classes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This faculty member is currently marked as unavailable to teach."
        )

    requested_subject_ids = list(set(assignment_data.curriculum_subject_ids))
    if not requested_subject_ids:
        return professor_profile

    # Validate subjects exist
    existing_subjects = database_session.query(CurriculumSubject).filter(
        CurriculumSubject.subject_id.in_(requested_subject_ids)
    ).all()
    
    existing_subject_ids = {sub.subject_id for sub in existing_subjects}
    invalid_ids = [sid for sid in requested_subject_ids if sid not in existing_subject_ids]
    
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subjects not found in curriculum: {invalid_ids}",
        )

    from src.modules.faculty.models import GradebookEntry as GBE
    already_assigned = database_session.query(GBE.curriculum_subject_id).filter(
        GBE.faculty_account_id == assignment_data.faculty_account_id,
        GBE.curriculum_subject_id.in_(requested_subject_ids)
    ).all()
    
    assigned_subject_ids = {row[0] for row in already_assigned}
    subjects_to_assign = [sid for sid in requested_subject_ids if sid not in assigned_subject_ids]

    if not subjects_to_assign:
        return professor_profile

    # THE LOAD BALANCER CHECK
    new_total_load = professor_profile.current_teaching_load + len(subjects_to_assign)
    if new_total_load > professor_profile.maximum_teaching_load:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Overload Alert: Assigning {len(subjects_to_assign)} new subjects exceeds the max limit of {professor_profile.maximum_teaching_load}."
        )

    # Bulk insert into Gradebook
    database_session.bulk_save_objects([
        models.GradebookEntry(
            faculty_account_id=assignment_data.faculty_account_id,
            curriculum_subject_id=subject_id,
            student_account_id=None,
            completion_status="NOT STARTED",
        )
        for subject_id in subjects_to_assign
    ])

    professor_profile.current_teaching_load = new_total_load
    database_session.commit()
    database_session.refresh(professor_profile)

    audit_service.log_event(
        database_session=database_session,
        event_type="FACULTY_BULK_ASSIGNED",
        actor_id=actor_id,
        actor_email=actor_email,
        target_type="faculty",
        target_id=assignment_data.faculty_account_id,
        ip_address=ip_address,
        payload={
            "assigned_subject_ids": subjects_to_assign,
            "new_load":             professor_profile.current_teaching_load,
            "max_load":             professor_profile.maximum_teaching_load,
        },
    )

    return professor_profile


def evaluate_and_assign_faculty_load(
    database_session: Session,
    assignment_data: schemas.FacultyAssignmentRequest,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> models.FacultyProfile:

    # Step 1: Find the professor
    professor_profile = repository.fetch_faculty_profile_by_account(
        database_session=database_session,
        target_account_id=assignment_data.faculty_account_id
    )

    if professor_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Faculty profile not found."
        )

    if professor_profile.is_available_for_classes == False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This faculty member is currently marked as unavailable to teach."
        )

    if professor_profile.current_teaching_load >= professor_profile.maximum_teaching_load:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Overload Alert: This professor is already teaching their maximum limit of {professor_profile.maximum_teaching_load} classes."
        )

    subject = database_session.query(CurriculumSubject).filter(
        CurriculumSubject.subject_id == assignment_data.curriculum_subject_id
    ).first()

    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject ID {assignment_data.curriculum_subject_id} not found in curriculum.",
        )

    from src.modules.faculty.models import GradebookEntry as GBE
    already_assigned = database_session.query(GBE).filter(
        GBE.faculty_account_id == assignment_data.faculty_account_id,
        GBE.curriculum_subject_id == assignment_data.curriculum_subject_id,
    ).first()

    if already_assigned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This professor is already assigned to that subject.",
        )

    new_entry = models.GradebookEntry(
        faculty_account_id=assignment_data.faculty_account_id,
        curriculum_subject_id=assignment_data.curriculum_subject_id,
        student_account_id=None, 
        completion_status="NOT STARTED",
    )
    database_session.add(new_entry)

    # Step 4d: Increment the load counter
    professor_profile.current_teaching_load += 1

    database_session.commit()
    database_session.refresh(professor_profile)

    #  Audit emit 
    audit_service.log_event(
        database_session=database_session,
        event_type="FACULTY_ASSIGNED",
        actor_id=actor_id,
        actor_email=actor_email,
        target_type="faculty",
        target_id=assignment_data.faculty_account_id,
        ip_address=ip_address,
        payload={
            "subject_id":   assignment_data.curriculum_subject_id,
            "new_load":     professor_profile.current_teaching_load,
            "max_load":     professor_profile.maximum_teaching_load,
        },
    )

    return professor_profile


def securely_update_student_grade(
    database_session: Session,
    faculty_account_id: int,
    grade_data: schemas.GradeSubmissionRequest,
    actor_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> models.GradebookEntry:


    grade_record = repository.fetch_specific_grade_record(
        database_session=database_session,
        student_id=grade_data.student_account_id,
        faculty_id=faculty_account_id,
        subject_id=grade_data.curriculum_subject_id
    )

    if grade_record is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security Violation: You are not assigned to teach this student for this specific subject."
        )

    before = {
        "midterm_grade":     grade_record.midterm_grade,
        "final_grade":       grade_record.final_grade,
        "completion_status": grade_record.completion_status,
        "override_reason":   grade_record.override_reason,
    }

    if grade_data.midterm_grade is not None:
        grade_record.midterm_grade = grade_data.midterm_grade

    if grade_data.final_grade is not None:
        if grade_data.final_grade != grade_record.system_grade:
            if not grade_data.override_reason or grade_data.override_reason.strip() == "":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="An explicit override reason is mandatory when modifying the system-computed final grade."
                )
        grade_record.final_grade = grade_data.final_grade
        grade_record.override_reason = grade_data.override_reason
        
    if grade_data.system_grade is not None:
        grade_record.system_grade = grade_data.system_grade

    if grade_data.completion_status:
        grade_record.completion_status = grade_data.completion_status

    # Step 5: Save to the database
    database_session.commit()
    database_session.refresh(grade_record)

    # ── Audit emit 
    audit_service.log_event(
        database_session=database_session,
        event_type="GRADE_MODIFIED",
        actor_id=faculty_account_id,
        actor_email=actor_email,
        target_type="student",
        target_id=grade_data.student_account_id,
        ip_address=ip_address,
        payload={
            "subject_id": grade_data.curriculum_subject_id,
            "before":     before,
            "after": {
                "midterm_grade":     grade_record.midterm_grade,
                "final_grade":       grade_record.final_grade,
                "completion_status": grade_record.completion_status,
            },
        },
    )

    return grade_record

def fetch_class_roster(
    database_session: Session,
    faculty_account_id: int,
    subject_code: str
) -> list[schemas.ClassRosterResponse]:
    return repository.fetch_class_roster_by_subject(database_session, faculty_account_id, subject_code)

def sync_offline_grades(
    database_session: Session,
    faculty_account_id: int,
    sync_data: schemas.SyncGradesRequest,
    actor_email: str,
    ip_address: str
) -> dict:
   
    synced_count = 0
    skipped_count = 0
    skipped_keys = []

    from src.modules.enrollment.models import CurriculumSubject
    from src.modules.audit.models import AuditEvent
    from datetime import datetime, timezone

    for update in sync_data.updates:
        subject_id = update.curriculum_subject_id
        if not subject_id and update.subject_code:
            subj = database_session.query(CurriculumSubject).filter(
                CurriculumSubject.subject_code == update.subject_code
            ).first()
            if subj:
                subject_id = subj.subject_id

        if not subject_id:
            continue

        composite_key = f"{update.student_account_id}__{subject_id}"

        if update.client_updated_at is not None:
            last_server_write = (
                database_session.query(AuditEvent)
                .filter(
                    AuditEvent.event_type == "GRADE_MODIFIED",
                    AuditEvent.target_type == "student",
                    AuditEvent.target_id == str(update.student_account_id),
                )
                .order_by(AuditEvent.created_at.desc())
                .first()
            )

            if last_server_write and last_server_write.created_at:
                server_ts = last_server_write.created_at
                if server_ts.tzinfo is None:
                    server_ts = server_ts.replace(tzinfo=timezone.utc)
                server_epoch_ms = int(server_ts.timestamp() * 1000)

                import json
                try:
                    audit_payload = json.loads(last_server_write.payload) if isinstance(last_server_write.payload, str) else (last_server_write.payload or {})
                except (json.JSONDecodeError, TypeError):
                    audit_payload = {}

                audit_subject_id = audit_payload.get("subject_id")

                if audit_subject_id == subject_id and update.client_updated_at < server_epoch_ms:
                    skipped_count += 1
                    skipped_keys.append(composite_key)
                    continue
        try:
            update.curriculum_subject_id = subject_id
            securely_update_student_grade(
                database_session=database_session,
                faculty_account_id=faculty_account_id,
                grade_data=update,
                actor_email=actor_email,
                ip_address=ip_address
            )
            synced_count += 1
        except HTTPException:
            pass 

    return {
        "synced_count": synced_count,
        "skipped_count": skipped_count,
        "skipped_keys": skipped_keys,
    }


# ── Triage Alerts 

def fetch_triage_alerts(
    database_session: Session,
    faculty_account_id: int,
) -> list[dict]:
    
    from src.modules.enrollment.models import CurriculumSubject, StudentProfile
    from src.modules.auth.models import UserAccount
    from src.modules.support.models import SupportTicket

    alerts: list[dict] = []

    failing_rows = (
        database_session.query(models.GradebookEntry, CurriculumSubject, StudentProfile)
        .join(CurriculumSubject, models.GradebookEntry.curriculum_subject_id == CurriculumSubject.subject_id)
        .outerjoin(StudentProfile, models.GradebookEntry.student_account_id == StudentProfile.student_account_id)
        .filter(
            models.GradebookEntry.faculty_account_id == faculty_account_id,
            models.GradebookEntry.student_account_id != None,
        )
        .all()
    )

    for grade, subject, profile in failing_rows:
        sys_g = grade.system_grade or 0
        fin_g = grade.final_grade or 0
        if sys_g >= 3.0 or fin_g >= 3.0:
            student_name = f"{profile.first_name} {profile.last_name}" if profile else "Unknown"
            alerts.append({
                "alert_type": "ADVISING",
                "severity": "warning",
                "title": "Advising Alert",
                "description": f"{student_name} is at risk of failing {subject.subject_code} — {subject.subject_title}.",
                "subject_code": subject.subject_code,
                "student_name": student_name,
                "ticket_id": None,
            })

    taught_subject_ids = (
        database_session.query(models.GradebookEntry.curriculum_subject_id)
        .filter(models.GradebookEntry.faculty_account_id == faculty_account_id)
        .distinct()
        .all()
    )
    taught_ids = [row[0] for row in taught_subject_ids]

    if taught_ids:
        student_ids_under_faculty = (
            database_session.query(models.GradebookEntry.student_account_id)
            .filter(
                models.GradebookEntry.faculty_account_id == faculty_account_id,
                models.GradebookEntry.student_account_id != None,
            )
            .distinct()
            .all()
        )
        student_ids = [row[0] for row in student_ids_under_faculty]

        if student_ids:
            open_tickets = (
                database_session.query(SupportTicket, StudentProfile)
                .outerjoin(StudentProfile, SupportTicket.student_account_id == StudentProfile.student_account_id)
                .filter(
                    SupportTicket.student_account_id.in_(student_ids),
                    SupportTicket.ticket_status == "OPEN",
                    SupportTicket.ai_predicted_category.ilike("%grade%"),
                )
                .all()
            )

            for ticket, profile in open_tickets:
                student_name = f"{profile.first_name} {profile.last_name}" if profile else "Unknown"
                alerts.append({
                    "alert_type": "GRADE_DISPUTE",
                    "severity": "critical",
                    "title": "Grade Rectification",
                    "description": f"{student_name} filed a dispute: {ticket.issue_subject}",
                    "subject_code": None,
                    "student_name": student_name,
                    "ticket_id": ticket.ticket_id,
                })

    return alerts


# ── Consultation Slots 

def get_consultation_slots(
    database_session: Session,
    faculty_account_id: int,
) -> list[models.ConsultationSlot]:
    return (
        database_session.query(models.ConsultationSlot)
        .filter(models.ConsultationSlot.faculty_account_id == faculty_account_id)
        .order_by(models.ConsultationSlot.slot_id)
        .all()
    )


def create_consultation_slot(
    database_session: Session,
    faculty_account_id: int,
    slot_data: schemas.ConsultationSlotCreate,
) -> models.ConsultationSlot:
    new_slot = models.ConsultationSlot(
        faculty_account_id=faculty_account_id,
        available_date=slot_data.available_date,
        start_time=slot_data.start_time,
        end_time=slot_data.end_time,
    )
    database_session.add(new_slot)
    database_session.commit()
    database_session.refresh(new_slot)
    return new_slot


def delete_consultation_slot(
    database_session: Session,
    faculty_account_id: int,
    slot_id: int,
) -> None:
    slot = (
        database_session.query(models.ConsultationSlot)
        .filter(
            models.ConsultationSlot.slot_id == slot_id,
            models.ConsultationSlot.faculty_account_id == faculty_account_id,
        )
        .first()
    )
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found.")
    database_session.delete(slot)
    database_session.commit()

def update_consultation_slot(
    database_session: Session,
    faculty_account_id: int,
    slot_id: int,
    slot_data: schemas.ConsultationSlotUpdate,
) -> models.ConsultationSlot:
    slot = (
        database_session.query(models.ConsultationSlot)
        .filter(
            models.ConsultationSlot.slot_id == slot_id,
            models.ConsultationSlot.faculty_account_id == faculty_account_id,
        )
        .first()
    )
    if not slot:
        raise HTTPException(status_code=404, detail="Slot not found.")
    
    if slot_data.available_date is not None:
        slot.available_date = slot_data.available_date
    if slot_data.start_time is not None:
        slot.start_time = slot_data.start_time
    if slot_data.end_time is not None:
        slot.end_time = slot_data.end_time
    if slot_data.is_active is not None:
        slot.is_active = slot_data.is_active

    database_session.commit()
    database_session.refresh(slot)
    return slot


# ── Consultation Requests 

def get_consultation_requests(
    database_session: Session,
    faculty_account_id: int,
) -> list[dict]:
    from src.modules.enrollment.models import StudentProfile

    rows = (
        database_session.query(models.ConsultationRequest, StudentProfile)
        .outerjoin(StudentProfile, models.ConsultationRequest.student_account_id == StudentProfile.student_account_id)
        .filter(models.ConsultationRequest.faculty_account_id == faculty_account_id)
        .order_by(models.ConsultationRequest.created_at.desc())
        .all()
    )

    result = []
    for req, profile in rows:
        student_name = f"{profile.first_name} {profile.last_name}" if profile else "Unknown Student"
        result.append({
            "request_id": req.request_id,
            "student_name": student_name,
            "reason": req.reason,
            "booking_date": req.booking_date,
            "start_time": req.start_time,
            "end_time": req.end_time,
            "status": req.status,
            "created_at": req.created_at.isoformat() if req.created_at else None,
        })
    return result


def update_consultation_request_status(
    database_session: Session,
    faculty_account_id: int,
    request_id: int,
    new_status: str,
) -> models.ConsultationRequest:
    if new_status not in ("APPROVED", "DECLINED"):
        raise HTTPException(status_code=400, detail="Status must be APPROVED or DECLINED.")

    req = (
        database_session.query(models.ConsultationRequest)
        .filter(
            models.ConsultationRequest.request_id == request_id,
            models.ConsultationRequest.faculty_account_id == faculty_account_id,
        )
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Consultation request not found.")

    req.status = new_status
    database_session.commit()
    database_session.refresh(req)
    return req

# ── Student Consultation Features ──

def get_faculty_for_consultation(database_session: Session) -> list[dict]:
    from src.modules.faculty.models import FacultyProfile, ConsultationSlot
    
    rows = (
        database_session.query(FacultyProfile)
        .join(ConsultationSlot, FacultyProfile.faculty_account_id == ConsultationSlot.faculty_account_id)
        .filter(ConsultationSlot.is_active == True)
        .distinct()
        .all()
    )
    
    return [
        {
            "account_id": p.faculty_account_id,
            "faculty_name": f"{p.first_name} {p.last_name}",
            "academic_department": p.academic_department
        }
        for p in rows
    ]

def generate_available_30min_chunks(
    database_session: Session,
    faculty_account_id: int,
    target_date: str
) -> list[dict]:
    import datetime
    
    slots = (
        database_session.query(models.ConsultationSlot)
        .filter(
            models.ConsultationSlot.faculty_account_id == faculty_account_id,
            models.ConsultationSlot.available_date == target_date,
            models.ConsultationSlot.is_active == True
        )
        .all()
    )

    if not slots:
        return []

    # Get existing requests to block off booked slots
    existing_requests = (
        database_session.query(models.ConsultationRequest)
        .filter(
            models.ConsultationRequest.faculty_account_id == faculty_account_id,
            models.ConsultationRequest.booking_date == target_date,
            models.ConsultationRequest.status.in_(["PENDING", "APPROVED"])
        )
        .all()
    )
    
    booked_times = {(req.start_time, req.end_time) for req in existing_requests}

    available_chunks = []
    
    for slot in slots:
        try:
            start_dt = datetime.datetime.strptime(slot.start_time, "%H:%M")
            end_dt = datetime.datetime.strptime(slot.end_time, "%H:%M")
        except ValueError:
            continue
            
        current_dt = start_dt
        while current_dt + datetime.timedelta(minutes=30) <= end_dt:
            next_dt = current_dt + datetime.timedelta(minutes=30)
            chunk_start = current_dt.strftime("%H:%M")
            chunk_end = next_dt.strftime("%H:%M")
            
            if (chunk_start, chunk_end) not in booked_times:
                available_chunks.append({
                    "start_time": chunk_start,
                    "end_time": chunk_end
                })
                
            current_dt = next_dt

    # Sort chunks by time
    available_chunks.sort(key=lambda x: x["start_time"])
    return available_chunks

def create_student_consultation_request(
    database_session: Session,
    student_account_id: int,
    booking_data: schemas.StudentConsultationBookingCreate
) -> models.ConsultationRequest:
    
    # Verify the chunk is available
    chunks = generate_available_30min_chunks(
        database_session=database_session,
        faculty_account_id=booking_data.faculty_account_id,
        target_date=booking_data.booking_date
    )
    
    is_available = any(
        c["start_time"] == booking_data.start_time and c["end_time"] == booking_data.end_time
        for c in chunks
    )
    
    if not is_available:
        raise HTTPException(status_code=409, detail="This time slot is no longer available.")
        
    # Get any slot_id to fulfill the foreign key constraint (the first active slot for that day)
    
    parent_slot = (
        database_session.query(models.ConsultationSlot)
        .filter(
            models.ConsultationSlot.faculty_account_id == booking_data.faculty_account_id,
            models.ConsultationSlot.available_date == booking_data.booking_date,
            models.ConsultationSlot.is_active == True,
            models.ConsultationSlot.start_time <= booking_data.start_time,
            models.ConsultationSlot.end_time >= booking_data.end_time
        )
        .first()
    )
    
    if not parent_slot:
        raise HTTPException(status_code=400, detail="Faculty no longer has a schedule covering this slot.")

    new_request = models.ConsultationRequest(
        slot_id=parent_slot.slot_id,
        student_account_id=student_account_id,
        faculty_account_id=booking_data.faculty_account_id,
        reason=booking_data.reason,
        booking_date=booking_data.booking_date,
        start_time=booking_data.start_time,
        end_time=booking_data.end_time,
        status="PENDING"
    )
    
    database_session.add(new_request)
    database_session.commit()
    database_session.refresh(new_request)
    
    from src.modules.faculty.models import FacultyProfile
    profile = database_session.query(FacultyProfile).filter(FacultyProfile.faculty_account_id == booking_data.faculty_account_id).first()
    faculty_name = f"{profile.first_name} {profile.last_name}" if profile else "Unknown Faculty"
    
    return {
        "request_id": new_request.request_id,
        "faculty_name": faculty_name,
        "reason": new_request.reason,
        "booking_date": new_request.booking_date,
        "start_time": new_request.start_time,
        "end_time": new_request.end_time,
        "status": new_request.status,
        "created_at": new_request.created_at.isoformat() if new_request.created_at else None,
    }

def get_student_consultation_requests(
    database_session: Session,
    student_account_id: int
) -> list[dict]:
    from src.modules.faculty.models import FacultyProfile
    
    rows = (
        database_session.query(models.ConsultationRequest, FacultyProfile)
        .outerjoin(FacultyProfile, models.ConsultationRequest.faculty_account_id == FacultyProfile.faculty_account_id)
        .filter(models.ConsultationRequest.student_account_id == student_account_id)
        .order_by(models.ConsultationRequest.created_at.desc())
        .all()
    )
    
    result = []
    for req, profile in rows:
        faculty_name = f"{profile.first_name} {profile.last_name}" if profile else "Unknown Faculty"
        result.append({
            "request_id": req.request_id,
            "faculty_name": faculty_name,
            "reason": req.reason,
            "booking_date": req.booking_date,
            "start_time": req.start_time,
            "end_time": req.end_time,
            "status": req.status,
            "created_at": req.created_at.isoformat() if req.created_at else None,
        })
    return result