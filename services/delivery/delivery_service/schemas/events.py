from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


Channel = Literal["push", "email", "web"]


class NotificationCreatedEvent(BaseModel):
    event_id: UUID
    notification_id: UUID
    topic_id: UUID
    created_by: UUID
    payload: dict[str, Any]
    scheduled_at: datetime | None
    created_at: datetime


class DeliverySucceededEvent(BaseModel):
    event_id: UUID
    notification_id: UUID
    user_id: UUID
    channel: Channel
    attempt_id: UUID
    delivered_at: datetime


class DeliveryFailedEvent(BaseModel):
    event_id: UUID
    notification_id: UUID
    user_id: UUID
    channel: Channel
    attempt_id: UUID
    error_code: str
    error_message: str
    failed_at: datetime
