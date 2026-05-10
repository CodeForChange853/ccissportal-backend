from fastapi import APIRouter, Depends
from typing import List
from pydantic import BaseModel

router = APIRouter(prefix="/notifications", tags=["notifications"])

class NotificationResponse(BaseModel):
    notification_id: int
    title: str
    message: str
    priority: str
    is_read: bool

@router.get("/my", response_model=List[NotificationResponse])
async def get_my_notifications():
    # Return empty list for now to silence 404s
    return []

@router.post("/mark-read/{notification_id}")
async def mark_as_read(notification_id: int):
    return {"status": "success"}
