from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Response, status

from subscriptions_service.api.dependencies import get_subscriptions_service
from subscriptions_service.core.dependencies import get_connection, get_current_user_id
from subscriptions_service.repositories.records import SubscriptionRecord
from subscriptions_service.schemas.subscriptions import (
    MySubscriptionsResponse,
    QuietHoursResponse,
    SubscribeRequest,
    SubscriptionPreferencesResponse,
    SubscriptionResponse,
    UpdateSubscriptionRequest,
)
from subscriptions_service.services.subscriptions import SubscriptionsService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _to_subscription_response(subscription: SubscriptionRecord) -> SubscriptionResponse:
    quiet_hours = None
    if subscription.preferences.quiet_hours_start and subscription.preferences.quiet_hours_end:
        quiet_hours = QuietHoursResponse(
            start=subscription.preferences.quiet_hours_start,
            end=subscription.preferences.quiet_hours_end,
        )

    return SubscriptionResponse(
        id=str(subscription.id),
        topic_id=str(subscription.topic_id),
        is_active=subscription.is_active,
        preferences=SubscriptionPreferencesResponse(
            channels=subscription.preferences.channels,
            quiet_hours=quiet_hours,
            timezone=subscription.preferences.timezone,
        ),
    )


@router.get("/me", response_model=MySubscriptionsResponse)
async def my_subscriptions(
    limit: int = Query(default=50, ge=1, le=500),
    cursor: str | None = Query(default=None),
    user_id: UUID = Depends(get_current_user_id),
    conn: asyncpg.Connection = Depends(get_connection),
    service: SubscriptionsService = Depends(get_subscriptions_service),
) -> MySubscriptionsResponse:
    subscriptions, next_cursor = await service.list_my(
        conn=conn,
        user_id=user_id,
        limit=limit,
        cursor=cursor,
    )
    return MySubscriptionsResponse(
        items=[_to_subscription_response(subscription) for subscription in subscriptions],
        next_cursor=next_cursor,
    )


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def subscribe(
    payload: SubscribeRequest,
    response: Response,
    user_id: UUID = Depends(get_current_user_id),
    conn: asyncpg.Connection = Depends(get_connection),
    service: SubscriptionsService = Depends(get_subscriptions_service),
) -> SubscriptionResponse:
    subscription, created = await service.subscribe(
        conn=conn,
        user_id=user_id,
        topic_id=payload.topic_id,
    )
    if not created:
        response.status_code = status.HTTP_200_OK

    return _to_subscription_response(subscription)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    subscription_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    conn: asyncpg.Connection = Depends(get_connection),
    service: SubscriptionsService = Depends(get_subscriptions_service),
) -> Response:
    await service.unsubscribe(conn=conn, user_id=user_id, subscription_id=subscription_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: UUID,
    payload: UpdateSubscriptionRequest,
    user_id: UUID = Depends(get_current_user_id),
    conn: asyncpg.Connection = Depends(get_connection),
    service: SubscriptionsService = Depends(get_subscriptions_service),
) -> SubscriptionResponse:
    updated = await service.update_subscription(
        conn=conn,
        user_id=user_id,
        subscription_id=subscription_id,
        is_active=payload.is_active,
        preferences_patch=payload.preferences,
    )
    return _to_subscription_response(updated)
