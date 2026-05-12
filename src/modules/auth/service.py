import json
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from passlib.context import CryptContext

# Grouping all your database models together here!
from src.modules.enrollment.models import StudentProfile, CurriculumSubject
from src.modules.faculty.models import FacultyProfile, GradebookEntry

from . import schemas, repository, models
from src.core.security import create_secure_access_token
from src.modules.settings.service import get_active_passkey
from src.modules.audit import service as audit_service

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_text_password: str, hashed_password: str) -> bool:
    return password_context.verify(plain_text_password, hashed_password)

def hash_new_password(plain_text_password: str) -> str:
    return password_context.hash(plain_text_password)

def process_user_login(
    database_session: Session,
    credentials: schemas.LoginCredentialsRequest,
    ip_address: Optional[str] = None,
) -> schemas.SuccessfulLoginResponse:
    """Validates credentials and returns a signed JWT on success."""

    user_account = repository.fetch_user_by_email(
        database_session=database_session,
        target_email=credentials.email_address,
    )

    if user_account is None:
        audit_service.log_event(
            database_session=database_session,
            event_type="LOGIN_FAILED",
            actor_email=credentials.email_address,
            ip_address=ip_address,
            payload={"reason": "account_not_found"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="We could not find an account with that email address.",
        )

    if not user_account.is_active_account:
        if user_account.violation_count >= 3:
            audit_service.log_event(
                database_session=database_session,
                event_type="LOGIN_BLOCKED_BANNED",
                actor_id=user_account.account_id,
                actor_email=user_account.email_address,
                ip_address=ip_address,
                payload={"reason": "violation_threshold_reached", "strikes": user_account.violation_count},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ACCOUNT_BANNED",
                    "message": "Your account has been permanently banned due to repeated violations of academic integrity and harassment policies."
                }
            )

        audit_service.log_event(
            database_session=database_session,
            event_type="LOGIN_FAILED",
            actor_id=user_account.account_id,
            actor_email=user_account.email_address,
            ip_address=ip_address,
            payload={"reason": "account_deactivated"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Please contact campus support.",
        )

    if not verify_password(credentials.plain_text_password, user_account.hashed_password):
        audit_service.log_event(
            database_session=database_session,
            event_type="LOGIN_FAILED",
            actor_id=user_account.account_id,
            actor_email=user_account.email_address,
            ip_address=ip_address,
            payload={"reason": "wrong_password"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The password provided is incorrect.",
        )

    from src.modules.settings.models import SystemSettings
    sys_settings = database_session.query(SystemSettings).filter(SystemSettings.settings_id == 1).first()
    if sys_settings and sys_settings.is_maintenance_mode:
        if user_account.account_role != "ADMIN":
            audit_service.log_event(
                database_session=database_session,
                event_type="LOGIN_BLOCKED_MAINTENANCE",
                actor_id=user_account.account_id,
                actor_email=user_account.email_address,
                ip_address=ip_address,
                payload={"role": user_account.account_role},
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "maintenance": True,
                    "reason": sys_settings.maintenance_reason or "Neural Infrastructure Recalibration",
                    "message": sys_settings.maintenance_message or "The NexEnroll AI Core is currently undergoing deep-layer synchronization to optimize semestral load balancing and ensure total data integrity."
                }
            )

    secure_access_token = create_secure_access_token(
        data={
            "sub":  user_account.email_address,
            "role": user_account.account_role,
            "id":   user_account.account_id,
        }
    )

    audit_service.log_event(
        database_session=database_session,
        event_type="LOGIN_SUCCESS",
        actor_id=user_account.account_id,
        actor_email=user_account.email_address,
        ip_address=ip_address,
        payload={"role": user_account.account_role},
    )

    return schemas.SuccessfulLoginResponse(
        access_token=secure_access_token,
        account_role=user_account.account_role,
        account_id=user_account.account_id,
    )

def process_user_registration(
    database_session: Session,
    registration_data: schemas.RegistrationRequest,
    ip_address: Optional[str] = None,
    skip_passkey: bool = False,
) -> schemas.SuccessfulLoginResponse:
 
    if registration_data.account_role == "STUDENT" and not skip_passkey:
        try:
            active_passkey = get_active_passkey(database_session=database_session)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="System settings not initialised. Please contact the administrator.",
            )

        if registration_data.passkey_code != active_passkey:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration denied: Invalid student passkey.",
            )

    existing_account = repository.get_user_account_by_email(
        database_session=database_session,
        email_address=registration_data.email_address,
    )

    if existing_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An account for '{registration_data.email_address}' already exists.",
        )

    hashed_password = hash_new_password(registration_data.plain_text_password)
    new_user_account = models.UserAccount(
        email_address=registration_data.email_address,
        hashed_password=hashed_password,
        account_role=registration_data.account_role,
        is_active_account=True,
    )

    try:
        # ATOMIC TRANSACTION START
        database_session.add(new_user_account)
        database_session.flush() 
        saved_account = new_user_account

        if saved_account.account_role == "STUDENT":
            computed_year = 1
            computed_sem = 1
            matched_subs = []
            is_irregular = False
            is_ai_verified = bool(registration_data.id_verification_token)

            if registration_data.cor_verification_token:
                from src.modules.document_processing.repository import fetch_scan_by_token
                scan_rec = fetch_scan_by_token(database_session, registration_data.cor_verification_token)
                if scan_rec and scan_rec.extracted_ai_data:
                    try:
                        payload = json.loads(scan_rec.extracted_ai_data)
                        ex_data = payload.get("extracted_data", {})
                        subjects_raw = ex_data.get("subjects", [])
                        scanned_subject_codes = [s["code"] for s in subjects_raw if s.get("code")]
                        
                        cor_name = (ex_data.get("full_name") or "").lower().strip()
                        cor_id = (ex_data.get("student_id") or "").lower().strip()
                        claim_name = (f"{registration_data.first_name} {registration_data.last_name}").lower().strip()
                        claim_id = (registration_data.student_number or "").lower().strip()
                        
                        if cor_name and cor_name != claim_name:
                             raise HTTPException(
                                 status_code=403, 
                                 detail="SECURITY VIOLATION: The uploaded document belongs to another user. Unauthorized use of academic records is a strictly prohibited violation and has been logged for potential blacklisting."
                             )
                        
                        if cor_id and claim_id and cor_id != claim_id:
                             raise HTTPException(
                                 status_code=403, 
                                 detail="SECURITY VIOLATION: Student ID mismatch detected. Document use must match account identity. Continued violations will lead to permanent account suspension."
                             )
                        
                        if scanned_subject_codes:
                            matched_subs = database_session.query(CurriculumSubject).filter(
                                CurriculumSubject.subject_code.in_(scanned_subject_codes)
                            ).all()
                            if matched_subs:
                                year_levels = {s.target_year_level for s in matched_subs}
                                computed_year = max(year_levels)
                                highest_year_subs = [s for s in matched_subs if s.target_year_level == computed_year]
                                computed_sem = max(s.target_semester for s in highest_year_subs)
                                if len(year_levels) > 1:
                                    is_irregular = True
                    except HTTPException:
                        raise
                    except Exception:
                        pass

            student_profile = StudentProfile(
                student_account_id=saved_account.account_id,
                first_name=registration_data.first_name or "Student",
                last_name=registration_data.last_name or "",
                student_number=registration_data.student_number or None,
                current_course=registration_data.course or "BSCS",
                current_year_level=computed_year,
                current_semester=computed_sem,
                is_ai_verified=is_ai_verified,
                is_irregular=is_irregular,
            )
            database_session.add(student_profile)

            if computed_year > 1 or computed_sem > 1:
                course_name = student_profile.current_course.upper()
                normalized_course = "BSCS" if "COMPUTER SCIENCE" in course_name else ("BSIT" if "INFORMATION TECHNOLOGY" in course_name else course_name)
                historic_subs = database_session.query(CurriculumSubject).filter(
                    (CurriculumSubject.target_year_level < computed_year) |
                    ((CurriculumSubject.target_year_level == computed_year) & (CurriculumSubject.target_semester < computed_sem))
                ).filter(CurriculumSubject.course == normalized_course).all()

                first_faculty = database_session.query(FacultyProfile).first()
                fallback_faculty_id = first_faculty.faculty_account_id if first_faculty else None

                if fallback_faculty_id:
                    for subj in (historic_subs + matched_subs):
                        status_str = "PASSED" if subj in historic_subs else "NOT STARTED"
                        grade_val = 2.0 if subj in historic_subs else None
                        
                        assigned = database_session.query(GradebookEntry).filter(
                            GradebookEntry.curriculum_subject_id == subj.subject_id,
                            GradebookEntry.student_account_id == None
                        ).first()
                        fac_id = assigned.faculty_account_id if assigned else fallback_faculty_id
                        
                        database_session.add(GradebookEntry(
                            student_account_id=saved_account.account_id,
                            faculty_account_id=fac_id,
                            curriculum_subject_id=subj.subject_id,
                            midterm_grade=grade_val,
                            system_grade=grade_val,
                            final_grade=grade_val,
                            completion_status=status_str
                        ))

        elif saved_account.account_role == "FACULTY":
            fallback_emp_id = f"FAC-{saved_account.account_id}"
            from src.modules.settings.models import SystemSettings
            sys_settings = database_session.query(SystemSettings).filter(SystemSettings.settings_id == 1).first()
            global_max_load = sys_settings.global_max_teaching_load if sys_settings else 4

            faculty_profile = FacultyProfile(
                faculty_account_id=saved_account.account_id,
                first_name=registration_data.first_name or "Faculty",
                last_name=registration_data.last_name or "",
                employee_id=registration_data.employee_id or fallback_emp_id,
                academic_department=registration_data.academic_department or "General",
                maximum_teaching_load=global_max_load,
                current_teaching_load=0,
                is_available_for_classes=True,
            )
            database_session.add(faculty_profile)

        secure_access_token = create_secure_access_token(
            data={"sub": saved_account.email_address, "role": saved_account.account_role, "id": saved_account.account_id}
        )

        audit_service.log_event(
            database_session=database_session,
            event_type="USER_REGISTERED",
            actor_id=saved_account.account_id,
            actor_email=saved_account.email_address,
            ip_address=ip_address,
            payload={"role": saved_account.account_role},
        )

        database_session.commit()
        database_session.refresh(saved_account)

        return schemas.SuccessfulLoginResponse(
            access_token=secure_access_token,
            account_role=saved_account.account_role,
            account_id=saved_account.account_id,
        )

    except Exception as e:
        database_session.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

def validate_pre_registration(
    database_session: Session,
    data: schemas.PreRegistrationValidationRequest,
) -> bool:
    try:
        active_passkey = get_active_passkey(database_session=database_session)
    except HTTPException:
        raise HTTPException(status_code=500, detail="System settings not initialized.")

    if data.passkey_code != active_passkey:
        raise HTTPException(status_code=403, detail="Invalid system passkey.")

    existing_profile = database_session.query(StudentProfile).filter(StudentProfile.student_number == data.student_number).first()
    if existing_profile:
        raise HTTPException(status_code=400, detail="This student number is already registered.")

    return True