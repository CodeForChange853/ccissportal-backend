# backend-v2/src/modules/auth/repository.py

from sqlalchemy.orm import Session
from .models import UserAccount
from sqlalchemy.orm import Session
from . import models

def fetch_user_by_email(database_session: Session, target_email: str) -> UserAccount | None:
    """
    Searches the database for a user matching the provided email address.
    Because we added index=True to the email column in models.py, 
    this search is O(log n) and extremely fast.
    """
    return database_session.query(UserAccount).filter(UserAccount.email_address == target_email).first()

def get_user_account_by_email(database_session: Session, email_address: str):
    """
    Checks the database to see if an account with this email already exists.
    Returns the UserAccount object if found, or None if it is available.
    """
    return database_session.query(models.UserAccount).filter(
        models.UserAccount.email_address == email_address
    ).first()

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