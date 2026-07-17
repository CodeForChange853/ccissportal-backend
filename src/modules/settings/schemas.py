# backend-v2/src/modules/settings/schemas.py

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class SystemSettingsResponse(BaseModel):
 
    settings_id: int
    is_enrollment_open: bool
    global_max_teaching_load: int
    student_registration_passkey: str
    is_maintenance_mode: bool
    maintenance_reason: str | None = None
    wall_of_shame_cooldown_days: int = 60
    ojt_subject_code: str | None = None
    last_updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UpdateSystemSettingsRequest(BaseModel):

    is_enrollment_open: bool | None = None
    is_maintenance_mode: bool | None = None
    maintenance_reason: str | None = None

    global_max_teaching_load: int | None = Field(
        default=None,
        ge=1,   # Must be at least 1 subject
        le=10,  # Reasonable upper ceiling
        description="Maximum number of subjects any faculty member can be assigned.",
    )

    student_registration_passkey: str | None = Field(
        default=None,
        min_length=6,
        max_length=100,
        description="The passkey students must supply during self-registration.",
    )

    wall_of_shame_cooldown_days: int | None = Field(
        default=None,
        ge=7,
        le=365,
        description="Number of days a violator stays on the Wall of Shame before eligible for reform.",
    )

    ojt_subject_code: str | None = Field(
        default=None,
        max_length=50,
        description="Subject code that triggers the OJT Secretary clearance gate. Leave blank to disable.",
    )


class GeneratedPasskeyResponse(BaseModel):

    new_passkey: str