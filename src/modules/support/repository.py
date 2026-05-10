# backend-v2/src/modules/support/repository.py

from sqlalchemy.orm import Session
from .models import SupportTicket


def save_new_ticket(
    database_session: Session, new_ticket: SupportTicket
) -> SupportTicket:
    database_session.add(new_ticket)
    database_session.commit()
    database_session.refresh(new_ticket)
    return new_ticket


def fetch_student_tickets(
    database_session: Session, student_id: int
) -> list[SupportTicket]:
    return (
        database_session.query(SupportTicket)
        .filter(SupportTicket.student_account_id == student_id)
        .order_by(SupportTicket.created_at.desc())
        .all()
    )


def fetch_all_tickets(
    database_session: Session,
    skip: int = 0,
    limit: int = 50,
) -> list[SupportTicket]:

    return (
        database_session.query(SupportTicket)
        .order_by(SupportTicket.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def fetch_ticket_by_id(
    database_session: Session, ticket_id: int
) -> SupportTicket | None:
    return database_session.query(SupportTicket).filter(
        SupportTicket.ticket_id == ticket_id
    ).first()


def resolve_ticket(
    database_session: Session,
    ticket_id: int,
    resolution_note: str | None = None,
) -> SupportTicket | None:

    ticket = fetch_ticket_by_id(database_session, ticket_id)

    if ticket is None:
        return None

    ticket.ticket_status = "RESOLVED"

    # Save note if the column exists on the model.
    # This prevents a crash if the migration hasn't been run yet.
    if hasattr(ticket, "resolution_note"):
        ticket.resolution_note = resolution_note

    database_session.commit()
    database_session.refresh(ticket)
    return ticket

def reroute_ticket(
    database_session: Session,
    ticket_id: int,
    correct_category: str,
    resolution_note: str | None = None,
) -> SupportTicket | None:

    ticket = fetch_ticket_by_id(database_session, ticket_id)
    if ticket is None:
        return None

    ticket.ai_predicted_category = correct_category
    ticket.was_manually_rerouted = True
    ticket.ticket_status = "RESOLVED"

    if hasattr(ticket, "resolution_note") and resolution_note:
        ticket.resolution_note = resolution_note

    database_session.commit()
    database_session.refresh(ticket)
    return ticket


def fetch_resolved_tickets_for_retraining(
    database_session: Session,
) -> list[SupportTicket]:

    return (
        database_session.query(SupportTicket)
        .filter(
            SupportTicket.ticket_status == "RESOLVED",
            SupportTicket.was_manually_rerouted == True,
            SupportTicket.confidence_score.isnot(None),
        )
        .order_by(SupportTicket.created_at.asc())
        .all()
    )