from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class TopicRecord:
    id: UUID
    key: str
    name: str
    description: str | None
    created_at: datetime


@dataclass(slots=True)
class SubscriptionRecord:
    id: UUID
    user_id: UUID
    topic_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class SubscriberRecord:
    user_id: UUID
    subscription_id: UUID
