# backend-v2/src/modules/support/schemas.py


from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class TicketSubmissionRequest(BaseModel):
    issue_subject: str
    issue_description: str


class TicketResponse(BaseModel):
    """Returned to the student who owns the ticket."""
    ticket_id: int
    issue_subject: str
    issue_description: str
    ai_predicted_category: str
    ticket_status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdminTicketResponse(BaseModel):
    ticket_id: int
    student_account_id: int
    issue_subject: str
    issue_description: str
    ai_predicted_category: str
    confidence_score: Optional[float] = None       
    was_manually_rerouted: bool = False            
    ticket_status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ResolveTicketRequest(BaseModel):
    """
    NEW: Optional resolution note an Admin can attach when closing a ticket.
    The note field is optional so admins can resolve with one click if needed.
    """
    resolution_note: Optional[str] = None

class RerouteTicketRequest(BaseModel):
    """
    Body for PATCH /support/{id}/reroute.
    Admin supplies the correct department after reviewing a mis-triaged ticket.
    Setting this marks was_manually_rerouted=True, feeding the accuracy metric.
    """
    correct_category: str
    resolution_note: Optional[str] = None


class TelemetryStatsResponse(BaseModel):
    """
    Returned by GET /support/telemetry.
    Powers the AI Brain dashboard — pie chart + confidence trend line.
    """
    total_tickets: int
    ai_correct_count: int        
    manually_rerouted_count: int 
    accuracy_percentage: float   


    recent_confidence_scores: list[float]

    average_confidence: Optional[float] = None


class RetrainResultResponse(BaseModel):
    """Returned by POST /support/retrain-model."""
    status: str         
    trained_on: int     
    reason: Optional[str] = None