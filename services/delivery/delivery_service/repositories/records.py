from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class DeliveryAttemptRecord:
    id: UUID
    notification_id: UUID
    user_id: UUID
    channel: str
    payload: dict
    status: str
    attempt_no: int
    last_error_code: str | None
    last_error_message: str | None
    next_retry_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ProcessedEventRecord:
    event_id: UUID
    subject: str
    processed_at: datetime
