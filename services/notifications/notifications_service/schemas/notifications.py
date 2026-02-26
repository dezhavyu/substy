from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


NotificationStatus = Literal["created", "scheduled", "queued", "cancelled"]


class CreateNotificationRequest(BaseModel):
    topic_id: UUID
    payload: dict[str, Any]
    scheduled_at: datetime | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class NotificationResponse(BaseModel):
    id: UUID
    topic_id: UUID
    status: NotificationStatus
    scheduled_at: datetime | None
    created_at: datetime


class ListNotificationsResponse(BaseModel):
    items: list[NotificationResponse]
    next_cursor: str | None = None
