# backend-v2/src/modules/support/service.py


from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import repository, schemas, models
from .ml.triage_engine import SupportTriageEngine

triage_ai = SupportTriageEngine()


# Student-facing

def process_new_support_ticket(
    database_session: Session,
    student_id: int,
    ticket_data: schemas.TicketSubmissionRequest,
    actor_email: str | None = None,   # Added to prevent crash
    ip_address: str | None = None,    # Added to prevent crash
) -> models.SupportTicket:

    combined_text = f"{ticket_data.issue_subject} {ticket_data.issue_description}"


    predicted_department, confidence_score = triage_ai.predict_with_confidence(combined_text)

    new_ticket = models.SupportTicket(
        student_account_id=student_id,
        issue_subject=ticket_data.issue_subject,
        issue_description=ticket_data.issue_description,
        ai_predicted_category=predicted_department,
        confidence_score=confidence_score,  
        was_manually_rerouted=False,       
        ticket_status="OPEN",
    )

    saved_ticket = repository.save_new_ticket(
        database_session=database_session,
        new_ticket=new_ticket,
    )

    return saved_ticket


# Admin-facing — Reroute (AI Feedback Loop)

def process_ticket_reroute(
    database_session: Session,
    ticket_id: int,
    reroute_data: schemas.RerouteTicketRequest,
) -> models.SupportTicket:
 
    ticket = repository.fetch_ticket_by_id(
        database_session=database_session,
        ticket_id=ticket_id,
    )

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Support ticket #{ticket_id} not found.",
        )

    if ticket.ticket_status == "RESOLVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This ticket is already resolved and cannot be re-routed.",
        )

    updated_ticket = repository.reroute_ticket(
        database_session=database_session,
        ticket_id=ticket_id,
        correct_category=reroute_data.correct_category,
        resolution_note=reroute_data.resolution_note,
    )

    return updated_ticket


# Admin-facing — Telemetry

def fetch_telemetry_data(
    database_session: Session,
) -> schemas.TelemetryStatsResponse:
  
    from sqlalchemy import func as sql_func

    total_tickets = database_session.query(
        sql_func.count(SupportTicket.ticket_id)
    ).scalar() or 0

    manually_rerouted_count = database_session.query(
        sql_func.count(SupportTicket.ticket_id)
    ).filter(SupportTicket.was_manually_rerouted == True).scalar() or 0

    ai_correct_count = total_tickets - manually_rerouted_count

    accuracy_percentage = (
        round((ai_correct_count / total_tickets) * 100, 2)
        if total_tickets > 0 else 0.0
    )

    scored_tickets = (
        database_session.query(SupportTicket)
        .filter(SupportTicket.confidence_score.isnot(None))
        .order_by(SupportTicket.created_at.desc())
        .limit(30)
        .all()
    )
    scored_tickets = list(reversed(scored_tickets))

    recent_confidence_scores = [
        round(t.confidence_score * 100, 1) for t in scored_tickets
    ]

    average_confidence = (
        round(
            sum(t.confidence_score for t in scored_tickets) / len(scored_tickets) * 100,
            1,
        )
        if scored_tickets else None
    )

    return schemas.TelemetryStatsResponse(
        total_tickets=total_tickets,
        ai_correct_count=ai_correct_count,
        manually_rerouted_count=manually_rerouted_count,
        accuracy_percentage=accuracy_percentage,
        recent_confidence_scores=recent_confidence_scores,
        average_confidence=average_confidence,
    )

# Admin-facing — Model Retraining

def trigger_model_retrain(
    database_session: Session,
) -> schemas.RetrainResultResponse:

    labeled_tickets = repository.fetch_resolved_tickets_for_retraining(
        database_session=database_session,
    )


    training_texts = [
        f"{t.issue_subject} {t.issue_description}"
        for t in labeled_tickets
    ]
    training_labels = [
        t.ai_predicted_category  
        for t in labeled_tickets
    ]

    result = triage_ai.retrain_on_new_data(
        training_texts=training_texts,
        training_labels=training_labels,
    )

    return schemas.RetrainResultResponse(**result)