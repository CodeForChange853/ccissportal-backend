# backend-v2/src/core/security.py
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database_setup import get_database_session
from src.modules.auth.repository import fetch_user_by_email
from src.modules.auth.models import UserAccount

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/authentication/login")

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS  = 7


def create_secure_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    payload = {
        "sub":  data["sub"],
        "role": data.get("role"),
        "id":   data.get("id"),
        "type": "refresh",
    }
    payload["exp"] = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired. Please log in again.",
        )
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
        )
    return payload


# Base identity dependency
def get_current_user(
    token: str = Depends(oauth2_scheme),
    database_session: Session = Depends(get_database_session),
) -> UserAccount:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_email: str = payload.get("sub")
        if user_email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user_account = fetch_user_by_email(
        database_session=database_session, target_email=user_email
    )

    if user_account is None or not user_account.is_active_account:
        raise credentials_exception

    return user_account


def get_optional_current_user(
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="/authentication/login", auto_error=False)),
    database_session: Session = Depends(get_database_session),
) -> UserAccount | None:

    if not token:
        return None
    try:
        return get_current_user(token=token, database_session=database_session)
    except HTTPException:
        return None

def require_admin(
    current_user: UserAccount = Depends(get_current_user),
) -> UserAccount:

    if current_user.account_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Only administrators can perform this action.",
        )
    return current_user


def require_faculty(
    current_user: UserAccount = Depends(get_current_user),
) -> UserAccount:

    if current_user.account_role != "FACULTY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Only faculty members can perform this action.",
        )
    return current_user


def require_student(
    current_user: UserAccount = Depends(get_current_user),
) -> UserAccount:

    if current_user.account_role != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Only students can perform this action.",
        )
    return current_user


def require_secretary(
    current_user: UserAccount = Depends(get_current_user),
) -> UserAccount:

    if current_user.account_role != "SECRETARY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Only secretaries can perform this action.",
        )
    return current_user


def require_admin_or_secretary(
    current_user: UserAccount = Depends(get_current_user),
) -> UserAccount:

    if current_user.account_role not in ("ADMIN", "SECRETARY"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Administrator or Secretary access required.",
        )
    return current_user