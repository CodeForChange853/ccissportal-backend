from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class CompletionRequestCreate(BaseModel):
    gradebook_entry_id: int
    student_note:       str | None = Field(None, max_length=500)


class CompletionWorkflowAdvance(BaseModel):
    new_state:        str            = Field(
        ..., description="ROUTED_TO_FACULTY | AWAITING_ADMIN_POSTING | POSTED | REJECTED"
    )
    faculty_grade:    float | None = Field(None, ge=1.0, le=5.0)
    note:             str | None   = Field(None, max_length=500)
    rejection_reason: str | None   = Field(None, max_length=500)


class WorkflowNoteEntry(BaseModel):
    actor_id:   int | None = None
    actor_role: str
    state:      str
    note:       str | None = None
    timestamp:  str


class CompletionRequestResponse(BaseModel):
    id:                   int
    student_account_id:   int
    gradebook_entry_id:   int
    workflow_state:       str
    fee_verified_by:      int | None      = None
    fee_verified_at:      datetime | None = None
    faculty_final_grade:  float | None    = None
    faculty_submitted_at: datetime | None = None
    faculty_submitted_by: int | None      = None
    admin_posted_by:      int | None      = None
    admin_posted_at:      datetime | None = None
    rejected_by:          int | None      = None
    rejected_at:          datetime | None = None
    rejection_reason:     str | None      = None
    workflow_notes:       list | None     = None
    created_at:           datetime

    model_config = ConfigDict(from_attributes=True)
