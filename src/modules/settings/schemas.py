# backend-v2/src/modules/settings/schemas.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SystemSettingsResponse(BaseModel):
 
    settings_id: int
    is_enrollment_open: bool
    global_max_teaching_load: int
    student_registration_passkey: str
    is_maintenance_mode: bool
    maintenance_reason: Optional[str] = None
    last_updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UpdateSystemSettingsRequest(BaseModel):

    is_enrollment_open: Optional[bool] = None
    is_maintenance_mode: Optional[bool] = None
    maintenance_reason: Optional[str] = None

    global_max_teaching_load: Optional[int] = Field(
        default=None,
        ge=1,   # Must be at least 1 subject
        le=10,  # Reasonable upper ceiling
        description="Maximum number of subjects any faculty member can be assigned.",
    )

    student_registration_passkey: Optional[str] = Field(
        default=None,
        min_length=6,
        max_length=100,
        description="The passkey students must supply during self-registration.",
    )


class GeneratedPasskeyResponse(BaseModel):

    new_passkey: str