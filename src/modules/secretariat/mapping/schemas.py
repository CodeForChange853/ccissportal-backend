from pydantic import BaseModel, ConfigDict, Field
from typing import List
from datetime import datetime


class MappingEntry(BaseModel):
    previous_subject_code: str           = Field(..., max_length=50)
    previous_subject_name: str           = Field(..., max_length=255)
    previous_credit_units: int           = Field(..., ge=0)
    ccis_subject_id:       int | None = None
    recommended_action:    str           = Field(..., description="CREDIT | VALIDATE | REJECT")


class SubjectMappingDraftCreate(BaseModel):
    student_account_id:   int
    previous_institution: str              = Field(..., max_length=255)
    previous_program:     str              = Field(..., max_length=255)
    mapping_entries:      List[MappingEntry] = Field(default_factory=list)


class SubjectMappingDraftUpdate(BaseModel):
    previous_institution: str | None              = Field(None, max_length=255)
    previous_program:     str | None              = Field(None, max_length=255)
    mapping_entries:      List[MappingEntry] | None = None


class MappingApprovalDecision(BaseModel):
    decision:    str            = Field(..., description="APPROVED or REJECTED")
    admin_notes: str | None  = Field(None, max_length=500)


class SubjectMappingResponse(BaseModel):
    id:                       int
    student_account_id:       int
    prepared_by_secretary_id: int
    previous_institution:     str
    previous_program:         str
    mapping_entries:          list
    status:                   str
    admin_notes:              str | None      = None
    approved_by_admin_id:     int | None      = None
    approved_at:              datetime | None = None
    rejected_by_admin_id:     int | None      = None
    rejected_at:              datetime | None = None
    created_at:               datetime
    updated_at:               datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class MappingApprovalResult(BaseModel):
    mapping_id:        int
    status:            str
    subjects_credited: int
    message:           str
