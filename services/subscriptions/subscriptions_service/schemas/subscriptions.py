from uuid import UUID
from pydantic import BaseModel


class SubscribeRequest(BaseModel):
    topic_id: UUID


class UpdateSubscriptionRequest(BaseModel):
    is_active: bool


class SubscriptionResponse(BaseModel):
    id: str
    topic_id: str
    is_active: bool


class MySubscriptionsResponse(BaseModel):
    items: list[SubscriptionResponse]
    next_cursor: str | None = None


class InternalSubscribersResponseItem(BaseModel):
    user_id: str


class InternalSubscribersResponse(BaseModel):
    items: list[InternalSubscribersResponseItem]
    next_cursor: str | None = None
