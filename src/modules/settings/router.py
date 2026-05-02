# backend-v2/src/modules/settings/router.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.database_setup import get_database_session
from src.core.security import require_admin
from src.modules.auth.models import UserAccount

from . import schemas, service

settings_router = APIRouter(
    prefix="/settings",
    tags=["Global System Settings"],
)


@settings_router.get("/", response_model=schemas.SystemSettingsResponse)
def get_current_settings(
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):

    return service.fetch_all_settings(database_session=database_session)


@settings_router.patch("/", response_model=schemas.SystemSettingsResponse)
def deploy_settings_update(
    update_payload: schemas.UpdateSystemSettingsRequest,
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):

    return service.apply_settings_update(
        database_session=database_session,
        update_payload=update_payload,
    )


@settings_router.post("/generate-passkey", response_model=schemas.SystemSettingsResponse)
def rotate_student_passkey(
    database_session: Session = Depends(get_database_session),
    _admin: UserAccount = Depends(require_admin),
):

    return service.generate_new_passkey(database_session=database_session)