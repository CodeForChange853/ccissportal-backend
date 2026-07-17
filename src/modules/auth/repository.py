# backend-v2/src/modules/auth/repository.py

from sqlalchemy.orm import Session
from .models import UserAccount
from . import models
from src.modules.enrollment.models import StudentProfile
from src.modules.faculty.models import FacultyProfile


def fetch_user_by_email(database_session: Session, target_email: str) -> UserAccount | None:
    return (
        database_session.query(UserAccount)
        .filter(UserAccount.email_address == target_email)
        .first()
    )

def save_new_user_account(database_session: Session, new_account: UserAccount) -> UserAccount:
    """
    Takes a newly created user account object and permanently saves it to the database.
    """
    database_session.add(new_account)
    database_session.commit()
    database_session.refresh(new_account) 
    
    return new_account

def lock_user_account(database_session: Session, target_email: str) -> None:
    user_account = fetch_user_by_email(database_session, target_email)
    if user_account:
        user_account.is_active_account = False
        database_session.commit()


def fetch_user_by_id(database_session: Session, account_id: int) -> UserAccount | None:
    return database_session.query(UserAccount).filter(UserAccount.account_id == account_id).first()


def fetch_wall_of_shame_rows(
    database_session: Session,
) -> list[tuple[UserAccount, StudentProfile, FacultyProfile]]:
    return (
        database_session.query(UserAccount, StudentProfile, FacultyProfile)
        .outerjoin(StudentProfile, StudentProfile.student_account_id == UserAccount.account_id)
        .outerjoin(FacultyProfile, FacultyProfile.faculty_account_id == UserAccount.account_id)
        .filter(
            UserAccount.violation_count >= 3,
            UserAccount.is_active_account == False,
            UserAccount.removed_from_wall_at == None,
        )
        .all()
    )


def fetch_underwatch_rows(
    database_session: Session,
) -> list[tuple[UserAccount, StudentProfile, FacultyProfile]]:
    return (
        database_session.query(UserAccount, StudentProfile, FacultyProfile)
        .outerjoin(StudentProfile, StudentProfile.student_account_id == UserAccount.account_id)
        .outerjoin(FacultyProfile, FacultyProfile.faculty_account_id == UserAccount.account_id)
        .filter(
            UserAccount.violation_count >= 1,
            UserAccount.violation_count < 3,
            UserAccount.is_active_account == True,
        )
        .all()
    )