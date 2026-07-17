from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class SubjectPetitionCreate(BaseModel):
    petition_type:             str           = Field(..., description="OVERLOAD | SUBSTITUTE | LATE_ADD | CROSS_ENROLLMENT")
    subject_id:                int
    substitute_for_subject_id: int | None = None
    reason:                    str           = Field(..., min_length=10, max_length=2000)


class SecretaryPetitionAction(BaseModel):
    decision:        str           = Field(..., description="ENDORSE or REJECT")
    secretary_notes: str | None = Field(None, max_length=500)


class AdminPetitionDecision(BaseModel):
    decision:    str           = Field(..., description="APPROVE or REJECT")
    admin_notes: str | None = Field(None, max_length=500)


class SubjectPetitionResponse(BaseModel):
    id:                        int
    student_account_id:        int
    petition_type:             str
    subject_id:                int
    substitute_for_subject_id: int | None      = None
    reason:                    str
    status:                    str
    secretary_notes:           str | None      = None
    secretary_id:              int | None      = None
    secretary_acted_at:        datetime | None = None
    admin_notes:               str | None      = None
    admin_id:                  int | None      = None
    admin_acted_at:            datetime | None = None
    created_at:                datetime

    model_config = ConfigDict(from_attributes=True)
