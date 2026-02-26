from datetime import time

from pydantic import BaseModel


class SubscriberItem(BaseModel):
    user_id: str
    subscription_id: str
    channels: list[str]
    quiet_hours_start: time | None
    quiet_hours_end: time | None
    timezone: str


class SubscribersPage(BaseModel):
    items: list[SubscriberItem]
    next_cursor: str | None = None
