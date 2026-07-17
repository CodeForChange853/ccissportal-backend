
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from . import schemas, service
from src.core.database_setup import get_database_session
from src.core.security import require_admin, get_current_user, get_optional_current_user, require_secretary, create_refresh_token
from src.core.limiter import limiter

_COOKIE_KWARGS = dict(
    key="refresh_token",
    httponly=True,
    samesite="lax",
    secure=False,          # flip to True behind HTTPS in production
    max_age=7 * 24 * 3600,
    path="/authentication",
)
from src.modules.auth.models import UserAccount

auth_router = APIRouter(
    prefix="/authentication",
    tags=["User Authentication"],
)


@auth_router.post("/login", response_model=schemas.SuccessfulLoginResponse)
@limiter.limit("10/minute")
def submit_login_request(
    request: Request,
    response: Response,
    credentials: schemas.LoginCredentialsRequest,
    database_session: Session = Depends(get_database_session),
):
    result = service.process_user_login(
        database_session=database_session,
        credentials=credentials,
        ip_address=request.client.host if request.client else None,
    )
    refresh_token = create_refresh_token(data={
        "sub":  credentials.email_address,
        "role": result.account_role,
        "id":   result.account_id,
    })
    response.set_cookie(value=refresh_token, **_COOKIE_KWARGS)
    return result


@auth_router.post("/refresh", response_model=schemas.SuccessfulLoginResponse)
def refresh_access_token(
    request: Request,
    response: Response,
    database_session: Session = Depends(get_database_session),
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token present. Please log in again.",
        )
    result, new_refresh = service.process_token_refresh(
        database_session=database_session,
        refresh_token=refresh_token,
    )
    response.set_cookie(value=new_refresh, **_COOKIE_KWARGS)
    return result


@auth_router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="refresh_token", path="/authentication")
    return {"message": "Logged out successfully."}


@auth_router.post("/register", response_model=schemas.SuccessfulLoginResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
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


@auth_router.post("/validate-pre-reg")
def validate_pre_registration_credentials(
    data: schemas.PreRegistrationValidationRequest,
    database_session: Session = Depends(get_database_session),
):
    """Early check for student number and passkey."""
    return service.validate_pre_registration(
        database_session=database_session,
        data=data,
    )


# ── Secretary Provisioning ──

@auth_router.post("/provision-secretary", response_model=schemas.SecretaryProvisionResponse, status_code=status.HTTP_201_CREATED)
def provision_secretary(
    request: Request,
    provision_data: schemas.SecretaryProvisionRequest,
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    """Admin-only: creates a new Secretary account. No self-registration."""
    return service.provision_secretary_account(
        database_session=database_session,
        provision_data=provision_data,
        admin_id=_admin.account_id,
        admin_email=_admin.email_address,
        ip_address=request.client.host if request.client else None,
    )


# ── Wall of Shame Endpoints ──

@auth_router.get("/wall-of-shame", response_model=list[schemas.ViolatorPublicProfile])
def get_wall_of_shame(
    database_session: Session = Depends(get_database_session),
):
    return service.get_wall_of_shame(database_session)


@auth_router.post("/wall-of-shame/{account_id}/reform")
def reform_violator(
    account_id: int,
    request: Request,
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    return service.reform_violator(
        database_session=database_session,
        account_id=account_id,
        admin_id=_admin.account_id,
        admin_email=_admin.email_address,
        ip_address=request.client.host if request.client else None,
    )


@auth_router.get("/wall-of-shame/underwatch", response_model=list[schemas.UnderwatchProfile])
def get_underwatch_users(
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):
    return service.get_underwatch_users(database_session)