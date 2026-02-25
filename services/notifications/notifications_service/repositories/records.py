from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class NotificationRecord:
    id: UUID
    topic_id: UUID
    payload: dict
    scheduled_at: datetime | None
    status: str
    created_by: UUID
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class OutboxEventRecord:
    id: UUID
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    payload: dict
    headers: dict
    created_at: datetime
    published_at: datetime | None
    publish_attempts: int
    last_error: str | None
