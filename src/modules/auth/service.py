from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from passlib.context import CryptContext
from src.modules.enrollment.models import StudentProfile
from src.modules.faculty.models import FacultyProfile
from . import schemas, repository, models
from src.core.security import create_secure_access_token
from src.modules.settings.service import get_active_passkey
from src.modules.audit import service as audit_service

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



# Utility helpers

def verify_password(plain_text_password: str, hashed_password: str) -> bool:
    return password_context.verify(plain_text_password, hashed_password)


def hash_new_password(plain_text_password: str) -> str:
    return password_context.hash(plain_text_password)

# Login


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



# Registration


def process_user_registration(
    database_session: Session,
    registration_data: schemas.RegistrationRequest,
    ip_address: Optional[str] = None,
    skip_passkey: bool = False,
) -> schemas.SuccessfulLoginResponse:
 
    # ── Step 1: Passkey Gate (Students only, unless bypassed) 
    if registration_data.account_role == "STUDENT" and not skip_passkey:

        
        try:
            active_passkey = get_active_passkey(database_session=database_session)
        except HTTPException:
           
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="System settings not initialised. "
                       "Please contact the administrator.",
            )

        if registration_data.passkey_code != active_passkey:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration denied: Invalid student passkey. "
                       "Please obtain the current passkey from your department.",
            )

    #   Duplicate email guard 
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

    saved_account = repository.save_new_user_account(
        database_session=database_session,
        new_account=new_user_account,
    )

    if saved_account.account_role == "STUDENT":
        # AI-Inferred Academic Level
        computed_year = 1
        computed_sem = 1
        matched_subs = []

        if registration_data.document_verification_token:
            from src.modules.document_processing.repository import fetch_scan_by_token
            import json
            from src.modules.enrollment.models import CurriculumSubject
            
            scan_rec = fetch_scan_by_token(database_session, registration_data.document_verification_token)
            if scan_rec and scan_rec.extracted_ai_data:
                try:
                    payload = json.loads(scan_rec.extracted_ai_data)
                    subjects_raw = payload.get("extracted_data", {}).get("subjects", [])
                    scanned_subject_codes = [s["code"] for s in subjects_raw if s.get("code")]
                    
                    if scanned_subject_codes:
                        matched_subs = database_session.query(CurriculumSubject).filter(
                            CurriculumSubject.subject_code.in_(scanned_subject_codes)
                        ).all()
                        
                        if matched_subs:
                            computed_year = max(s.target_year_level for s in matched_subs)
                            highest_year_subs = [s for s in matched_subs if s.target_year_level == computed_year]
                            computed_sem = max(s.target_semester for s in highest_year_subs)
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
        )
        database_session.add(student_profile)
        database_session.commit()

        # Historical Grade Auto-Loader
        if computed_year > 1 or computed_sem > 1:
            from src.modules.enrollment.models import CurriculumSubject
            from src.modules.faculty.models import GradebookEntry, FacultyProfile
            
            course_name = student_profile.current_course.upper()
            if "COMPUTER SCIENCE" in course_name:
                normalized_course = "BSCS"
            elif "INFORMATION TECHNOLOGY" in course_name:
                normalized_course = "BSIT"
            else:
                normalized_course = course_name

            historic_subs = database_session.query(CurriculumSubject).filter(
                (CurriculumSubject.target_year_level < computed_year) |
                ((CurriculumSubject.target_year_level == computed_year) & (CurriculumSubject.target_semester < computed_sem))
            ).filter(CurriculumSubject.course == normalized_course).all()

            first_faculty = database_session.query(FacultyProfile).first()
            fallback_faculty_id = first_faculty.faculty_account_id if first_faculty else None

            if fallback_faculty_id and historic_subs:
                for subj in historic_subs:
                    assigned = database_session.query(GradebookEntry).filter(
                        GradebookEntry.curriculum_subject_id == subj.subject_id,
                        GradebookEntry.student_account_id == None
                    ).first()
                    
                    fac_id = assigned.faculty_account_id if assigned else fallback_faculty_id
                    
                    gh_entry = GradebookEntry(
                        student_account_id=saved_account.account_id,
                        faculty_account_id=fac_id,
                        curriculum_subject_id=subj.subject_id,
                        midterm_grade=2.0,
                        system_grade=2.0,
                        final_grade=2.0,
                        completion_status="PASSED"
                    )
                    database_session.add(gh_entry)
                
                database_session.commit()

            if fallback_faculty_id and matched_subs:
                for subj in matched_subs:
                    assigned = database_session.query(GradebookEntry).filter(
                        GradebookEntry.curriculum_subject_id == subj.subject_id,
                        GradebookEntry.student_account_id == None
                    ).first()
                    
                    fac_id = assigned.faculty_account_id if assigned else fallback_faculty_id
                    
                    curr_entry = GradebookEntry(
                        student_account_id=saved_account.account_id,
                        faculty_account_id=fac_id,
                        curriculum_subject_id=subj.subject_id,
                        midterm_grade=None,
                        system_grade=None,
                        final_grade=None,
                        completion_status="NOT STARTED"
                    )
                    database_session.add(curr_entry)
                
                database_session.commit()

    elif saved_account.account_role == "FACULTY":
        fallback_emp_id = f"FAC-{saved_account.account_id}"
        faculty_profile = FacultyProfile(
            faculty_account_id=saved_account.account_id,
            first_name=registration_data.first_name or "Faculty",
            last_name=registration_data.last_name or "",
            employee_id=registration_data.employee_id or fallback_emp_id,
            academic_department=registration_data.academic_department or "General",
            maximum_teaching_load=4,
            current_teaching_load=0,
            is_available_for_classes=True,
        )
        database_session.add(faculty_profile)
        database_session.commit()
    #  Return a signed token 
    secure_access_token = create_secure_access_token(
        data={
            "sub":  saved_account.email_address,
            "role": saved_account.account_role,
            "id":   saved_account.account_id,
        }
    )

    audit_service.log_event(
        database_session=database_session,
        event_type="USER_REGISTERED",
        actor_id=saved_account.account_id,
        actor_email=saved_account.email_address,
        ip_address=ip_address,
        payload={"role": saved_account.account_role},
    )

    return schemas.SuccessfulLoginResponse(
        access_token=secure_access_token,
        account_role=saved_account.account_role,
        account_id=saved_account.account_id,
    )