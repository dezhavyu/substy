from dataclasses import dataclass
from datetime import datetime, time
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
    preferences: "SubscriptionPreferencesRecord"
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class SubscriberRecord:
    user_id: UUID
    subscription_id: UUID
    channels: list[str]
    quiet_hours_start: time | None
    quiet_hours_end: time | None
    timezone: str


@dataclass(slots=True)
class SubscriptionPreferencesRecord:
    channels: list[str]
    quiet_hours_start: time | None
    quiet_hours_end: time | None
    timezone: str
    updated_at: datetime
