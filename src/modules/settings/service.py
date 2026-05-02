# backend-v2/src/modules/settings/service.py

import random
import string
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import repository, schemas

from src.modules.audit import service as audit_service


# Internal helper — used by other modules (enrollment, auth)

def _require_settings_row(database_session: Session):

    settings_row = repository.fetch_system_settings(database_session)
    if settings_row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System settings have not been initialised. "
                   "Please run seed_database.py to create the default configuration.",
        )
    return settings_row


# Public functions called by other modules
def get_enrollment_status(database_session: Session) -> bool:
    settings_row = _require_settings_row(database_session)
    return settings_row.is_enrollment_open


def get_active_passkey(database_session: Session) -> str:
  
    settings_row = _require_settings_row(database_session)
    return settings_row.student_registration_passkey


def get_max_teaching_load(database_session: Session) -> int:
  
    settings_row = _require_settings_row(database_session)
    return settings_row.global_max_teaching_load


# CRUD for the Command Center router

def fetch_all_settings(
    database_session: Session,
) -> schemas.SystemSettingsResponse:
    settings_row = _require_settings_row(database_session)
    return schemas.SystemSettingsResponse.model_validate(settings_row)


def apply_settings_update(
    database_session: Session,
    update_payload: schemas.UpdateSystemSettingsRequest,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> schemas.SystemSettingsResponse:
  
    settings_row = _require_settings_row(database_session)

    update_dict = update_payload.model_dump(exclude_none=True)

    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No settings fields were provided in the request body.",
        )

    updated_row = repository.update_system_settings(
        database_session=database_session,
        settings_row=settings_row,
        updated_fields=update_dict,
    )

    audit_service.log_event(
        database_session=database_session,
        event_type="SETTING_CHANGED",
        actor_id=actor_id,
        actor_email=actor_email,
        target_type="setting",
        ip_address=ip_address,
        payload={"changed_fields": list(update_dict.keys())},
    )

    return schemas.SystemSettingsResponse.model_validate(updated_row)


def generate_new_passkey(
    database_session: Session,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> schemas.SystemSettingsResponse:

    year = __import__("datetime").datetime.now().year
    random_suffix = "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )
    new_passkey = f"UNIV-{year}-{random_suffix}"

    settings_row = _require_settings_row(database_session)

    updated_row = repository.update_system_settings(
        database_session=database_session,
        settings_row=settings_row,
        updated_fields={"student_registration_passkey": new_passkey},
    )

    audit_service.log_event(
        database_session=database_session,
        event_type="PASSKEY_ROTATED",
        actor_id=actor_id,
        actor_email=actor_email,
        target_type="setting",
        ip_address=ip_address,
        payload={"new_passkey_prefix": f"UNIV-{year}-***"},
    )

    return schemas.SystemSettingsResponse.model_validate(updated_row)