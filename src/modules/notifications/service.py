from sqlalchemy.orm import Session
from . import repository
from .models import Notification


def get_notifications_for_user(db: Session, user_id: int) -> tuple[list[Notification], int]:
    notifications = repository.fetch_for_user(db, user_id, limit=20)
    unread_count = repository.get_unread_count(db, user_id)
    return notifications, unread_count


def mark_notification_read(db: Session, notification_id: int, user_id: int) -> Notification | None:
    return repository.mark_read(db, notification_id, user_id)


def mark_all_notifications_read(db: Session, user_id: int) -> int:
    return repository.mark_all_read(db, user_id)


def emit_enrollment_notification(db: Session, student_account_id: int, decision: str) -> None:
    if decision == "APPROVED":
        title = "Enrollment Approved"
        message = (
            "Your enrollment request has been approved. "
            "Check the Enrollment Status tab for your confirmed subjects."
        )
        notif_type = "ENROLLMENT_APPROVED"
    else:
        title = "Enrollment Not Approved"
        message = (
            "Your enrollment request was not approved. "
            "See the Enrollment Status tab for reviewer notes, then resubmit."
        )
        notif_type = "ENROLLMENT_REJECTED"

    try:
        repository.create_notification(
            db=db,
            recipient_id=student_account_id,
            title=title,
            message=message,
            notif_type=notif_type,
        )
    except Exception as exc:
        print(f"⚠️  Notification emission failed (non-blocking): {exc}")
