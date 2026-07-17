from sqlalchemy.orm import Session
from .models import Notification


def create_notification(
    db: Session,
    recipient_id: int,
    title: str,
    message: str,
    notif_type: str,
) -> Notification:
    notif = Notification(
        recipient_account_id=recipient_id,
        title=title,
        message=message,
        notif_type=notif_type,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def fetch_for_user(db: Session, user_id: int, limit: int = 20) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.recipient_account_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )


def get_unread_count(db: Session, user_id: int) -> int:
    return (
        db.query(Notification)
        .filter(
            Notification.recipient_account_id == user_id,
            Notification.is_read == False,
        )
        .count()
    )


def mark_read(db: Session, notification_id: int, user_id: int) -> Notification | None:
    notif = (
        db.query(Notification)
        .filter(
            Notification.notification_id == notification_id,
            Notification.recipient_account_id == user_id,
        )
        .first()
    )
    if notif is None:
        return None
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


def mark_all_read(db: Session, user_id: int) -> int:
    updated = (
        db.query(Notification)
        .filter(
            Notification.recipient_account_id == user_id,
            Notification.is_read == False,
        )
        .update({"is_read": True})
    )
    db.commit()
    return updated
