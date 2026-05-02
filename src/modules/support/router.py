# backend-v2/src/modules/support/router.py


from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from typing import List

from src.core.security import get_current_user, require_admin, require_student
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount
from src.modules.audit import service as audit_service

from . import schemas, service, repository

support_router = APIRouter(
    prefix="/support",
    tags=["Student Support & AI Triage"],
)


# STUDENT ROUTES

@support_router.post("/submit", response_model=schemas.TicketResponse)
def submit_support_ticket(
    request: Request,
    ticket_data: schemas.TicketSubmissionRequest,
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
  
    processed_ticket = service.process_new_support_ticket(
        database_session=database_session,
        student_id=current_user.account_id,
        ticket_data=ticket_data,
        actor_email=current_user.email_address,
        ip_address=request.client.host if request.client else None,
    )
    return processed_ticket


@support_router.get("/my-tickets", response_model=List[schemas.TicketResponse])
def view_my_tickets(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return repository.fetch_student_tickets(
        database_session=database_session,
        student_id=current_user.account_id,
    )


# ADMIN ROUTES

@support_router.get("/all", response_model=List[schemas.AdminTicketResponse])
def view_all_tickets(
    skip: int  = Query(default=0,  ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    database_session: Session = Depends(get_database_session),
    # NEW: client.js calls GET /support/all — this endpoint was missing entirely
    admin: UserAccount = Depends(require_admin),
):
   
    return repository.fetch_all_tickets(
        database_session=database_session,
        skip=skip,
        limit=limit,
    )

@support_router.get("/telemetry", response_model=schemas.TelemetryStatsResponse)
def get_ai_telemetry(
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
   
    return service.fetch_telemetry_data(database_session=database_session)

@support_router.patch("/{ticket_id}/resolve", response_model=schemas.TicketResponse)
def resolve_support_ticket(
    request: Request,
    ticket_id: int,
    resolve_data: schemas.ResolveTicketRequest,
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
   
    updated_ticket = repository.resolve_ticket(
        database_session=database_session,
        ticket_id=ticket_id,
        resolution_note=resolve_data.resolution_note,
    )

    if updated_ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No support ticket found with ID {ticket_id}.",
        )

    audit_service.log_event(
        database_session=database_session,
        event_type="TICKET_RESOLVED",
        actor_id=admin.account_id,
        actor_email=admin.email_address,
        target_type="ticket",
        target_id=ticket_id,
        ip_address=request.client.host if request.client else None,
        payload={"resolution_note": resolve_data.resolution_note},
    )

    return updated_ticket

@support_router.patch("/{ticket_id}/reroute", response_model=schemas.AdminTicketResponse)
def reroute_support_ticket(
    request: Request,
    ticket_id: int,
    reroute_data: schemas.RerouteTicketRequest,
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
   
    return service.process_ticket_reroute(
        database_session=database_session,
        ticket_id=ticket_id,
        reroute_data=reroute_data,
        actor_id=admin.account_id,
        actor_email=admin.email_address,
        ip_address=request.client.host if request.client else None,
    )




@support_router.post("/retrain-model", response_model=schemas.RetrainResultResponse)
def retrain_triage_model(
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
   
    return service.trigger_model_retrain(database_session=database_session)