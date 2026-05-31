from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/notifications", tags=["Notifications"])

class NotificationBase(BaseModel):
    user_id: int
    message: str
    is_read: bool = False

class NotificationCreate(NotificationBase):
    pass

class Notification(NotificationBase):
    id: int

fake_db_notifications = []

@router.get("/", response_model=List[Notification])
async def get_notifications():
    return fake_db_notifications

@router.post("/", response_model=Notification)
async def create_notification(notification: NotificationCreate):
    new_id = len(fake_db_notifications) + 1
    new_notification = Notification(id=new_id, **notification.model_dump())
    fake_db_notifications.append(new_notification)
    return new_notification