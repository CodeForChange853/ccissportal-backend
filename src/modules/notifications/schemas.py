from datetime import datetime, timezone
from pydantic import BaseModel, computed_field


class NotificationResponse(BaseModel):
    notification_id: int
    recipient_account_id: int
    title: str
    message: str
    notif_type: str
    is_read: bool
    created_at: datetime

    @computed_field
    @property
    def age(self) -> str:
        delta = datetime.now(timezone.utc) - self.created_at.replace(tzinfo=timezone.utc)
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            mins = seconds // 60
            return f"{mins} min ago"
        if seconds < 86400:
            hrs = seconds // 3600
            return f"{hrs} hr ago"
        days = seconds // 86400
        return f"{days}d ago"

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int
