from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class OJTSubmissionCreate(BaseModel):
    moa_document_ref:      str | None = Field(None, max_length=500)
    consent_form_ref:      str | None = Field(None, max_length=500)
    medical_clearance_ref: str | None = Field(None, max_length=500)
    additional_notes:      str | None = Field(None, max_length=1000)


class OJTVerificationUpdate(BaseModel):
    decision:        str            = Field(..., description="VERIFIED or REJECTED")
    secretary_notes: str | None  = Field(None, max_length=500)


class OJTSubmissionResponse(BaseModel):
    id:                       int
    student_account_id:       int
    moa_document_ref:         str | None = None
    consent_form_ref:         str | None = None
    medical_clearance_ref:    str | None = None
    additional_notes:         str | None = None
    submission_status:        str
    secretary_notes:          str | None = None
    verified_by_secretary_id: int | None = None
    verified_at:              datetime | None = None
    submitted_at:             datetime

    model_config = ConfigDict(from_attributes=True)


class OJTClearanceStatusResponse(BaseModel):
    student_account_id:   int
    ojt_clearance_status: str
    latest_submission:    OJTSubmissionResponse | None = None
