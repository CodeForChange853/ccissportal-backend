# backend-v2/src/modules/support/service.py

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import repository, schemas, models
from .models import SupportTicket
from src.modules.auth.models import UserAccount

BANNED_KEYWORDS = [
    "pussy", "dumb", "money", "dick", "sex", "stupid", "idiot",
    "fuck", "shit", "bitch", "asshole", "kill", "die", "harass"
]


def process_new_support_ticket(
    database_session: Session,
    student_id: int,
    ticket_data: schemas.TicketSubmissionRequest,
    actor_email: str | None = None,
    ip_address: str | None = None,
) -> models.SupportTicket:

    user = database_session.query(UserAccount).filter(UserAccount.account_id == student_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 1. Rate limiting: max 2 tickets per 24 hours
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    recent_count = database_session.query(models.SupportTicket).filter(
        models.SupportTicket.student_account_id == student_id,
        models.SupportTicket.created_at >= one_day_ago,
    ).count()

    if recent_count >= 2:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="TICKET_LIMIT_REACHED: You can only submit 2 support tickets per 24 hours to prevent spam.",
        )

    # 2. Content filtering
    combined_text = f"{ticket_data.issue_subject} {ticket_data.issue_description}".lower()
    found_violations = [w for w in BANNED_KEYWORDS if w in combined_text]

    if found_violations:
        user.violation_count += 1
        user.last_violation_at = datetime.now(timezone.utc)

        log_entry = {
            "offense": "Explicit/Harassing content in support ticket",
            "detected_at": datetime.utcnow().isoformat(),
            "keywords": found_violations,
        }
        existing_log = user.violation_log or []
        existing_log.append(log_entry)
        user.violation_log = existing_log

        if user.removed_from_wall_at is not None:
            user.removed_from_wall_at = None

        database_session.commit()

        if user.violation_count >= 3:
            user.is_active_account = False
            database_session.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ACCOUNT_BANNED",
                    "message": "Your account has been banned due to repeated violations of school rules and harassment policies. Please contact the Admin Office.",
                },
            )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "EXPLICIT_CONTENT_WARNING",
                "violation_count": user.violation_count,
                "message": "Explicit or harassing content detected. You are under supervision by the admin. If you reach 3 violations, your account will be permanently banned.",
            },
        )

    # 3. Save ticket with the department the student selected
    new_ticket = models.SupportTicket(
        student_account_id=student_id,
        department=ticket_data.department,
        issue_subject=ticket_data.issue_subject,
        issue_description=ticket_data.issue_description,
        was_manually_rerouted=False,
        ticket_status="OPEN",
    )

    return repository.save_new_ticket(
        database_session=database_session,
        new_ticket=new_ticket,
    )


def process_ticket_reroute(
    database_session: Session,
    ticket_id: int,
    reroute_data: schemas.RerouteTicketRequest,
    actor_id: int | None = None,
    actor_email: str | None = None,
    ip_address: str | None = None,
) -> models.SupportTicket:

    ticket = repository.fetch_ticket_by_id(database_session, ticket_id)

    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Support ticket #{ticket_id} not found.")

    if ticket.ticket_status == "RESOLVED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This ticket is already resolved and cannot be re-routed.")

    return repository.reroute_ticket(
        database_session=database_session,
        ticket_id=ticket_id,
        department=reroute_data.department,
        resolution_note=reroute_data.resolution_note,
    )
