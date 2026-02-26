from pydantic import BaseModel


class SubscriberItem(BaseModel):
    user_id: str


class SubscribersPage(BaseModel):
    items: list[SubscriberItem]
    next_cursor: str | None = None
