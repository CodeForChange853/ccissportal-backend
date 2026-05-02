# backend-v2/src/modules/settings/repository.py


from sqlalchemy.orm import Session
from .models import SystemSettings


def fetch_system_settings(database_session: Session) -> SystemSettings | None:

    return database_session.query(SystemSettings).filter(
        SystemSettings.settings_id == 1
    ).first()


def update_system_settings(
    database_session: Session,
    settings_row: SystemSettings,
    updated_fields: dict,
) -> SystemSettings:

    for field_name, new_value in updated_fields.items():
        if new_value is not None:
            setattr(settings_row, field_name, new_value)

    database_session.commit()
    database_session.refresh(settings_row)
    return settings_row