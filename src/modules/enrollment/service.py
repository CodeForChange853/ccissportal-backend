from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import repository, schemas, models
from src.modules.settings.service import get_enrollment_status
from src.modules.audit import service as audit_service


def process_student_enrollment_submission(
    database_session: Session,
    student_id: int,
    submission_data: schemas.StudentEnrollmentSubmission,
    actor_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> models.StudentEnrollmentRequest:

    # ── Step 1: Enrollment gate 
    if not get_enrollment_status(database_session=database_session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enrollment is currently closed. "
                   "Please check the university announcements for the next enrollment period.",
        )

    # ── Step 2: Year/semester validation for unscanned submissions 
    if not submission_data.document_verification_token:
        # Only enforce year 1 sem 1 for completely new students (no grades in history)
        from src.modules.faculty.models import GradebookEntry
        has_grades = database_session.query(GradebookEntry).filter(
            GradebookEntry.student_account_id == student_id
        ).first() is not None
        
        if not has_grades:
            if submission_data.target_year_level != 1 or submission_data.target_semester != 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New students without a scanned Certificate of Registration "
                           "must enroll in Year 1, Semester 1.",
                )

    # ── Step 3: Pull PrerequisiteChecker data from the existing scan record ───
    extracted_subjects  = None
    verification_result = None
    ai_recommendation   = None

    if submission_data.document_verification_token:
        try:
            import json
            from src.modules.document_processing.repository import fetch_scan_by_token

            scan = fetch_scan_by_token(
                database_session=database_session,
                token=submission_data.document_verification_token,
            )

            if scan and scan.extracted_ai_data:
                payload = json.loads(scan.extracted_ai_data)
                extracted_data = payload.get("extracted_data", {})

                subjects_raw = extracted_data.get("subjects", [])
                extracted_subjects = [s["code"] for s in subjects_raw if s.get("code")]

                cached_verification = payload.get("verification_result")
                cached_recommendation = payload.get("ai_recommendation")

                if cached_verification:
                    verification_result = cached_verification
                    ai_recommendation   = cached_recommendation

        except Exception as scan_err:
            print(f"⚠️  Could not load scan data: {scan_err}")

    # For Smart Enrollment without COR but WITH selected subjects
    if not submission_data.document_verification_token and submission_data.extracted_subjects:
        extracted_subjects = submission_data.extracted_subjects
    
    # Generate verification for either parsed COR subjects or Smart Enrollment subjects
    if extracted_subjects and not verification_result:
        try:
            from src.modules.enrollment.prerequisite_checker import PrerequisiteChecker
            checker = PrerequisiteChecker(database_session)
            rec     = checker.check_subjects(
                student_account_id=student_id,
                subject_codes=extracted_subjects,
            )
            verification_result = [
                {
                    "subject_id":      r.subject_id,
                    "subject_code":    r.subject_code,
                    "subject_title":   r.subject_title,
                    "credit_units":    r.credit_units,
                    "status":          r.status,
                    "prereq_code":     r.prereq_code,
                    "prereq_title":    r.prereq_title,
                    "prereq_status":   r.prereq_status,
                    "blocking_reason": r.blocking_reason,
                }
                for r in rec.subject_results
            ]
            ai_recommendation = {
                "verdict":          rec.verdict,
                "pass_rate":        rec.pass_rate,
                "available_count":  rec.available_count,
                "blocked_count":    rec.blocked_count,
                "pending_count":    rec.pending_count,
                "flagged_subjects": rec.flagged_subjects,
                "suggested_action": rec.suggested_action,
            }
        except Exception as checker_err:
            print(f"⚠️  Inline checker error: {checker_err}")

    # ── Step 4: Build and persist the enrollment record 
    new_enrollment_record = models.StudentEnrollmentRequest(
        student_account_id=student_id,
        target_year_level=submission_data.target_year_level,
        target_semester=submission_data.target_semester,
        document_verification_token=submission_data.document_verification_token,
        extracted_subjects=extracted_subjects,
        verification_result=verification_result,
        ai_recommendation=ai_recommendation,
        review_status="PENDING",
    )

    saved_record = repository.save_new_enrollment_request(
        database_session=database_session,
        new_request=new_enrollment_record,
    )

    # ── Audit emit 
    audit_service.log_event(
        database_session=database_session,
        event_type="ENROLLMENT_SUBMITTED",
        actor_id=student_id,
        actor_email=actor_email,
        target_type="enrollment",
        target_id=saved_record.request_id,
        ip_address=ip_address,
        payload={
            "year_level":       submission_data.target_year_level,
            "semester":         submission_data.target_semester,
            "has_cor":          bool(submission_data.document_verification_token),
            "subjects_found":   len(extracted_subjects) if extracted_subjects else 0,
            "ai_verdict":       ai_recommendation.get("verdict") if ai_recommendation else None,
        },
    )

    return saved_record


# ── Helper: materialize enrollment into gradebook entries ──────────────────

def _materialize_enrollment(
    database_session: Session,
    enrollment_request: models.StudentEnrollmentRequest,
) -> int:
    """
    When an enrollment request is APPROVED, create GradebookEntry rows
    with completion_status='ENROLLED' for each subject, linking the student
    to the faculty member already assigned to teach that subject.

    Returns the number of subjects materialized.
    """
    from src.modules.faculty.models import GradebookEntry, FacultyProfile
    from src.modules.enrollment.models import CurriculumSubject, StudentProfile

    student_id   = enrollment_request.student_account_id
    year_level   = enrollment_request.target_year_level
    semester     = enrollment_request.target_semester
    subject_codes = enrollment_request.extracted_subjects  # list[str] or None

    # ── Step 1: Resolve subjects to enroll ──
    if subject_codes:
        subjects = (
            database_session.query(CurriculumSubject)
            .filter(CurriculumSubject.subject_code.in_(subject_codes))
            .all()
        )
    else:
        # Fallback: enroll in all subjects for the target year/semester
        subjects = (
            database_session.query(CurriculumSubject)
            .filter(
                CurriculumSubject.target_year_level == year_level,
                CurriculumSubject.target_semester   == semester,
            )
            .all()
        )

    if not subjects:
        return 0

    # ── Step 2: Find a fallback faculty member ──
    first_faculty = database_session.query(FacultyProfile).first()
    fallback_faculty_id = first_faculty.faculty_account_id if first_faculty else None

    if not fallback_faculty_id:
        print("⚠️  No faculty profiles exist — cannot materialize enrollment.")
        return 0

    # ── Step 3: Deduplicate — skip subjects student already has a gradebook entry for ──
    existing_subject_ids = {
        row[0] for row in
        database_session.query(GradebookEntry.curriculum_subject_id)
        .filter(
            GradebookEntry.student_account_id == student_id,
            GradebookEntry.curriculum_subject_id.in_([s.subject_id for s in subjects]),
        )
        .all()
    }

    materialized = 0
    for subj in subjects:
        if subj.subject_id in existing_subject_ids:
            continue

        # Find the faculty assigned to teach this subject (template row with student_account_id=NULL)
        assigned_template = (
            database_session.query(GradebookEntry)
            .filter(
                GradebookEntry.curriculum_subject_id == subj.subject_id,
                GradebookEntry.student_account_id == None,
            )
            .first()
        )
        fac_id = assigned_template.faculty_account_id if assigned_template else fallback_faculty_id

        new_entry = GradebookEntry(
            student_account_id=student_id,
            faculty_account_id=fac_id,
            curriculum_subject_id=subj.subject_id,
            midterm_grade=None,
            system_grade=None,
            final_grade=None,
            completion_status="ENROLLED",
        )
        database_session.add(new_entry)
        materialized += 1

    # ── Step 4: Update the student's profile to reflect the new year/semester ──
    profile = (
        database_session.query(StudentProfile)
        .filter(StudentProfile.student_account_id == student_id)
        .first()
    )
    if profile:
        profile.current_year_level = year_level
        profile.current_semester   = semester

    if materialized > 0:
        database_session.commit()

    return materialized


def process_admin_enrollment_decision(
    database_session: Session,
    target_request_id: int,
    decision_data: schemas.AdminApprovalDecision,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> models.StudentEnrollmentRequest:

    target_request = repository.fetch_enrollment_request_by_id(
        database_session=database_session,
        request_id=target_request_id,
    )

    if target_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Enrollment request #{target_request_id} was not found.",
        )

    if target_request.review_status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This request has already been processed "
                   f"(status: {target_request.review_status}).",
        )

    if decision_data.decision_status not in {"APPROVED", "REJECTED"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid decision. Must be APPROVED or REJECTED.",
        )

    updated_request = repository.update_enrollment_status(
        database_session=database_session,
        enrollment_request=target_request,
        new_status=decision_data.decision_status,
        admin_notes=decision_data.admin_notes,
    )

    # ── NEW: Materialize enrollment into gradebook when APPROVED ──
    subjects_enrolled = 0
    if decision_data.decision_status == "APPROVED":
        subjects_enrolled = _materialize_enrollment(
            database_session=database_session,
            enrollment_request=updated_request,
        )

    event_type = (
        "ENROLLMENT_APPROVED"
        if decision_data.decision_status == "APPROVED"
        else "ENROLLMENT_REJECTED"
    )
    audit_service.log_event(
        database_session=database_session,
        event_type=event_type,
        actor_id=actor_id,
        actor_email=actor_email,
        target_type="enrollment",
        target_id=target_request_id,
        ip_address=ip_address,
        payload={
            "student_id":        target_request.student_account_id,
            "admin_notes":       decision_data.admin_notes,
            "subjects_enrolled": subjects_enrolled,
        },
    )

    return updated_request

def add_new_subject_to_curriculum(
    database_session: Session,
    subject_data: schemas.CurriculumSubjectCreateRequest,
) -> models.CurriculumSubject:

    existing = repository.fetch_subject_by_code(
        database_session=database_session,
        target_code=subject_data.subject_code,
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject code '{subject_data.subject_code}' already exists in the curriculum.",
        )

    new_subject = models.CurriculumSubject(
        subject_code=            subject_data.subject_code,
        subject_title=           subject_data.subject_title,
        credit_units=            subject_data.credit_units,
        target_year_level=       subject_data.target_year_level,
        target_semester=         subject_data.target_semester,
        course=                  subject_data.course,
        prerequisite_subject_id= subject_data.prerequisite_subject_id,
    )

    return repository.save_new_curriculum_subject(
        database_session=database_session,
        new_subject=new_subject,
    )


def remove_subject_from_curriculum(
    database_session: Session,
    target_subject_id: int,
) -> None:

    subject = repository.fetch_subject_by_id(
        database_session=database_session,
        subject_id=target_subject_id,
    )
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject ID {target_subject_id} not found in curriculum.",
        )

    repository.delete_subject_record(
        database_session=database_session,
        subject_record=subject,
    )

def bulk_process_enrollment_decision(
    database_session: Session,
    decision_data: schemas.BulkAdminApprovalDecision,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> int:

    requests_to_update = database_session.query(models.StudentEnrollmentRequest).filter(
        models.StudentEnrollmentRequest.request_id.in_(decision_data.request_ids),
        models.StudentEnrollmentRequest.review_status == "PENDING"
    ).all()

    if not requests_to_update:
        return 0

    processed_count = 0
    for req in requests_to_update:
        req.review_status = decision_data.decision_status
        if decision_data.admin_notes:
            req.admin_notes = decision_data.admin_notes
        processed_count += 1

        # ── NEW: Materialize enrollment into gradebook when APPROVED ──
        subjects_enrolled = 0
        if decision_data.decision_status == "APPROVED":
            subjects_enrolled = _materialize_enrollment(
                database_session=database_session,
                enrollment_request=req,
            )

        audit_service.log_event(
            database_session=database_session,
            event_type="ENROLLMENT_DECISION_SUBMITTED",
            actor_id=actor_id,
            actor_email=actor_email,
            target_type="enrollment_request",
            target_id=req.request_id,
            ip_address=ip_address,
            payload={
                "new_status": decision_data.decision_status,
                "bulk": True,
                "subjects_enrolled": subjects_enrolled,
            },
        )

    database_session.commit()
    return processed_count


def update_curriculum_subject(
    database_session: Session,
    target_subject_id: int,
    update_data: schemas.CurriculumSubjectUpdateRequest,
) -> models.CurriculumSubject:

    subject = repository.fetch_subject_by_id(
        database_session=database_session,
        subject_id=target_subject_id,
    )
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject ID {target_subject_id} not found in curriculum.",
        )

    # Prevent updating to an existing subject code
    if update_data.subject_code and update_data.subject_code != subject.subject_code:
        existing = repository.fetch_subject_by_code(
            database_session=database_session,
            target_code=update_data.subject_code,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subject code '{update_data.subject_code}' already exists.",
            )

    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(subject, key, value)

    database_session.commit()
    database_session.refresh(subject)
    return subject