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
    """
    Sync offline grade edits with last-write-wins conflict resolution.

    For each update, we check the audit log for the most recent server-side
    GRADE_MODIFIED event targeting the same (student, subject) pair.
    If the client's timestamp is older than the server's last write,
    the update is skipped as stale — preventing data collision when
    multiple devices sync concurrently.

    Returns a dict with synced_count, skipped_count, and skipped_keys.
    """
    synced_count = 0
    skipped_count = 0
    skipped_keys = []

    from src.modules.enrollment.models import CurriculumSubject
    from src.modules.audit.models import AuditEvent
    from datetime import datetime, timezone

    for update in sync_data.updates:
        # ── Step 1: Resolve subject ID from code if needed ──
        subject_id = update.curriculum_subject_id
        if not subject_id and update.subject_code:
            subj = database_session.query(CurriculumSubject).filter(
                CurriculumSubject.subject_code == update.subject_code
            ).first()
            if subj:
                subject_id = subj.subject_id

        if not subject_id:
            continue

        # ── Step 2: Last-write-wins conflict check ──
        composite_key = f"{update.student_account_id}__{subject_id}"

        if update.client_updated_at is not None:
            # Find the most recent server-side grade modification for this pair
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
                # Convert server timestamp to epoch-ms for comparison
                server_ts = last_server_write.created_at
                if server_ts.tzinfo is None:
                    server_ts = server_ts.replace(tzinfo=timezone.utc)
                server_epoch_ms = int(server_ts.timestamp() * 1000)

                # Also verify the audit payload matches this specific subject
                import json
                try:
                    audit_payload = json.loads(last_server_write.payload) if isinstance(last_server_write.payload, str) else (last_server_write.payload or {})
                except (json.JSONDecodeError, TypeError):
                    audit_payload = {}

                audit_subject_id = audit_payload.get("subject_id")

                if audit_subject_id == subject_id and update.client_updated_at < server_epoch_ms:
                    # Client edit is older than the last server write — skip as stale
                    skipped_count += 1
                    skipped_keys.append(composite_key)
                    continue

        # ── Step 3: Apply the grade update ──
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
            pass  # Skip invalid edits during bulk sync

    return {
        "synced_count": synced_count,
        "skipped_count": skipped_count,
        "skipped_keys": skipped_keys,
    }