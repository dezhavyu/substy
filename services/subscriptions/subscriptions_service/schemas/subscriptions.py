from datetime import time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator


DeliveryChannel = Literal["push", "email", "web"]


class SubscribeRequest(BaseModel):
    topic_id: UUID


class QuietHoursResponse(BaseModel):
    start: time
    end: time


class SubscriptionPreferencesResponse(BaseModel):
    channels: list[DeliveryChannel]
    quiet_hours: QuietHoursResponse | None
    timezone: str


class QuietHoursPatchRequest(BaseModel):
    start: time
    end: time


class SubscriptionPreferencesPatchRequest(BaseModel):
    channels: list[DeliveryChannel] | None = None
    quiet_hours: QuietHoursPatchRequest | None = None
    timezone: str | None = None

    @field_validator("channels")
    @classmethod
    def validate_channels_non_empty(cls, value: list[DeliveryChannel] | None) -> list[DeliveryChannel] | None:
        if value is not None and len(value) == 0:
            raise ValueError("channels must not be empty")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone_non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("timezone must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_non_empty_patch(self) -> "SubscriptionPreferencesPatchRequest":
        if self.channels is None and self.quiet_hours is None and self.timezone is None:
            raise ValueError("preferences patch must include at least one field")
        return self


class UpdateSubscriptionRequest(BaseModel):
    is_active: bool | None = None
    preferences: SubscriptionPreferencesPatchRequest | None = None

    @model_validator(mode="after")
    def validate_non_empty_patch(self) -> "UpdateSubscriptionRequest":
        if self.is_active is None and self.preferences is None:
            raise ValueError("patch must include at least one field")
        return self


class SubscriptionResponse(BaseModel):
    id: str
    topic_id: str
    is_active: bool
    preferences: SubscriptionPreferencesResponse


class MySubscriptionsResponse(BaseModel):
    items: list[SubscriptionResponse]
    next_cursor: str | None = None


class InternalSubscribersResponseItem(BaseModel):
    user_id: str
    subscription_id: str
    channels: list[DeliveryChannel]
    quiet_hours_start: time | None
    quiet_hours_end: time | None
    timezone: str


class InternalSubscribersResponse(BaseModel):
    items: list[InternalSubscribersResponseItem]
    next_cursor: str | None = None
