# backend-v2/src/modules/support/router.py

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from typing import List

from src.core.security import get_current_user, require_admin
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount
from src.modules.audit import service as audit_service

from . import schemas, service, repository, models

support_router = APIRouter(
    prefix="/support",
    tags=["Student Support"],
)


# ── Student routes ─────────────────────────────────────────────────────────────

@support_router.post("/submit", response_model=schemas.TicketResponse)
def submit_support_ticket(
    request: Request,
    ticket_data: schemas.TicketSubmissionRequest,
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return service.process_new_support_ticket(
        database_session=database_session,
        student_id=current_user.account_id,
        ticket_data=ticket_data,
        actor_email=current_user.email_address,
        ip_address=request.client.host if request.client else None,
    )


@support_router.get("/my-tickets", response_model=List[schemas.TicketResponse])
def view_my_tickets(
    database_session: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    return repository.fetch_student_tickets(
        database_session=database_session,
        student_id=current_user.account_id,
    )


# ── Admin routes ───────────────────────────────────────────────────────────────

@support_router.get("/all", response_model=List[schemas.AdminTicketResponse])
def view_all_tickets(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
    return repository.fetch_all_tickets(
        database_session=database_session,
        skip=skip,
        limit=limit,
    )


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


# ── Announcements ──────────────────────────────────────────────────────────────

@support_router.post("/announcements", response_model=schemas.AnnouncementResponse)
def create_announcement(
    data: schemas.AnnouncementCreate,
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
    announcement = models.SystemAnnouncement(
        title=data.title,
        body=data.body,
        type=data.type,
    )
    database_session.add(announcement)
    database_session.commit()
    database_session.refresh(announcement)
    return announcement


@support_router.delete("/announcements/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_announcement(
    announcement_id: int,
    database_session: Session = Depends(get_database_session),
    admin: UserAccount = Depends(require_admin),
):
    announcement = database_session.query(models.SystemAnnouncement).filter(
        models.SystemAnnouncement.id == announcement_id
    ).first()
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    database_session.delete(announcement)
    database_session.commit()
    return None
