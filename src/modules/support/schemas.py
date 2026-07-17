# backend-v2/src/modules/support/schemas.py

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Literal
from datetime import datetime

VALID_DEPARTMENTS = Literal["FINANCE", "REGISTRAR", "ACADEMIC AFFAIRS", "IT SUPPORT"]


class TicketSubmissionRequest(BaseModel):
    department: VALID_DEPARTMENTS
    issue_subject: str = Field(..., max_length=150)
    issue_description: str = Field(..., max_length=300)


class TicketResponse(BaseModel):
    """Returned to the student who submitted the ticket."""
    ticket_id: int
    department: str
    issue_subject: str
    issue_description: str
    ticket_status: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminTicketResponse(BaseModel):
    ticket_id: int
    student_account_id: int
    department: str
    issue_subject: str
    issue_description: str
    resolution_note: str | None = None
    was_manually_rerouted: bool = False
    ticket_status: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ResolveTicketRequest(BaseModel):
    resolution_note: str | None = Field(None, max_length=500)


class RerouteTicketRequest(BaseModel):
    """Admin corrects the department a student chose."""
    department: VALID_DEPARTMENTS
    resolution_note: str | None = Field(None, max_length=500)


class AnnouncementCreate(BaseModel):
    title: str = Field(..., max_length=200)
    body: str = Field(..., max_length=2000)
    type: str = Field(default="announcement", max_length=50)


class AnnouncementResponse(BaseModel):
    id: int
    title: str
    body: str
    type: str
    status: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
