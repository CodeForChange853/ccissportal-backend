
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from . import schemas, service
from src.core.database_setup import get_database_session
from src.core.security import require_admin, get_current_user, get_optional_current_user
from src.modules.auth.models import UserAccount

auth_router = APIRouter(
    prefix="/authentication",
    tags=["User Authentication"],
)


@auth_router.post("/login", response_model=schemas.SuccessfulLoginResponse)
def submit_login_request(
    request: Request,                                      
    credentials: schemas.LoginCredentialsRequest,
    database_session: Session = Depends(get_database_session),
):
    return service.process_user_login(
        database_session=database_session,
        credentials=credentials,
        ip_address=request.client.host if request.client else None,
    )


@auth_router.post("/register", response_model=schemas.SuccessfulLoginResponse, status_code=status.HTTP_201_CREATED)
def register_new_account(
    request: Request,                                         
    registration_data: schemas.RegistrationRequest,
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount | None = Depends(get_optional_current_user),
):

    is_admin_caller = (
        current_user is not None and
        current_user.account_role == "ADMIN"
    )
    return service.process_user_registration(
        database_session=database_session,
        registration_data=registration_data,
        ip_address=request.client.host if request.client else None,
        skip_passkey=is_admin_caller,
    )


@auth_router.get("/me", response_model=schemas.ProfileResponse)
def get_my_profile(
    current_user: UserAccount = Depends(get_current_user),
):
    return schemas.ProfileResponse(
        account_id=current_user.account_id,
        email_address=current_user.email_address,
        account_role=current_user.account_role,
        is_active_account=current_user.is_active_account,
    )