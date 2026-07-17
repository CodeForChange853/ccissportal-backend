from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class DocumentRequestCreate(BaseModel):
    document_type:  str           = Field(..., description="TRANSCRIPT | CERTIFICATION | DIPLOMA_AUTH | GOOD_MORAL | ENROLLMENT_CERT | OTHER")
    requestor_type: str           = Field(default="CURRENT_STUDENT", description="CURRENT_STUDENT | ALUMNI | EXTERNAL")
    purpose:        str           = Field(..., min_length=10, max_length=2000)
    document_notes: str | None = Field(None, max_length=500)


class ExternalDocumentRequestCreate(BaseModel):
    requestor_name:  str           = Field(..., max_length=255)
    requestor_email: str           = Field(..., max_length=255)
    requestor_type:  str           = Field(default="ALUMNI", description="ALUMNI | EXTERNAL")
    document_type:   str           = Field(..., description="TRANSCRIPT | CERTIFICATION | DIPLOMA_AUTH | GOOD_MORAL | ENROLLMENT_CERT | OTHER")
    purpose:         str           = Field(..., min_length=10, max_length=2000)
    document_notes:  str | None = Field(None, max_length=500)


class DocumentStatusAdvance(BaseModel):
    new_status:       str           = Field(..., description="PROCESSING | READY_FOR_PICKUP | RELEASED | REJECTED")
    secretary_notes:  str | None = Field(None, max_length=500)
    rejection_reason: str | None = Field(None, max_length=500)


class DocumentRequestResponse(BaseModel):
    id:                        int
    reference_number:          str
    requestor_account_id:      int | None      = None
    requestor_name:            str | None      = None
    requestor_email:           str | None      = None
    requestor_type:            str
    document_type:             str
    purpose:                   str
    document_notes:            str | None      = None
    status:                    str
    secretary_notes:           str | None      = None
    processed_by_secretary_id: int | None      = None
    processing_started_at:     datetime | None = None
    ready_at:                  datetime | None = None
    released_at:               datetime | None = None
    rejected_at:               datetime | None = None
    rejection_reason:          str | None      = None
    created_at:                datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentTrackResponse(BaseModel):
    """Minimal public response — no PII, only status info."""
    reference_number:      str
    document_type:         str
    requestor_type:        str
    status:                str
    processing_started_at: datetime | None = None
    ready_at:              datetime | None = None
    released_at:           datetime | None = None
    rejection_reason:      str | None      = None
    created_at:            datetime

    model_config = ConfigDict(from_attributes=True)
