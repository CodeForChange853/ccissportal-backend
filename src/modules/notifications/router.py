from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.security import get_current_user
from src.core.database_setup import get_database_session
from src.modules.auth.models import UserAccount
from . import service
from .schemas import NotificationListResponse, NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/my", response_model=NotificationListResponse)
def get_my_notifications(
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    notifications, unread_count = service.get_notifications_for_user(db, current_user.account_id)
    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(n) for n in notifications],
        unread_count=unread_count,
    )


@router.post("/mark-read/{notification_id}", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    notif = service.mark_notification_read(db, notification_id, current_user.account_id)
    if notif is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")
    return NotificationResponse.model_validate(notif)


@router.post("/mark-all-read")
def mark_all_notifications_read(
    db: Session = Depends(get_database_session),
    current_user: UserAccount = Depends(get_current_user),
):
    updated = service.mark_all_notifications_read(db, current_user.account_id)
    return {"marked_read": updated}
