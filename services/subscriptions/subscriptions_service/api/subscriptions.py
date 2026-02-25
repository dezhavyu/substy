from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Response, status

from subscriptions_service.api.dependencies import get_subscriptions_service
from subscriptions_service.core.dependencies import get_connection, get_current_user_id
from subscriptions_service.schemas.subscriptions import (
    MySubscriptionsResponse,
    SubscribeRequest,
    SubscriptionResponse,
    UpdateSubscriptionRequest,
)
from subscriptions_service.services.subscriptions import SubscriptionsService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


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
        items=[
            SubscriptionResponse(
                id=str(subscription.id),
                topic_id=str(subscription.topic_id),
                is_active=subscription.is_active,
            )
            for subscription in subscriptions
        ],
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

    return SubscriptionResponse(
        id=str(subscription.id),
        topic_id=str(subscription.topic_id),
        is_active=subscription.is_active,
    )


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
    updated = await service.update_status(
        conn=conn,
        user_id=user_id,
        subscription_id=subscription_id,
        is_active=payload.is_active,
    )
    return SubscriptionResponse(id=str(updated.id), topic_id=str(updated.topic_id), is_active=updated.is_active)
