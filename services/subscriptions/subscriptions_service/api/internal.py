from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query

from subscriptions_service.api.dependencies import get_subscriptions_service
from subscriptions_service.core.dependencies import get_connection
from subscriptions_service.schemas.subscriptions import InternalSubscribersResponse, InternalSubscribersResponseItem
from subscriptions_service.services.subscriptions import SubscriptionsService

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/topics/{topic_id}/subscribers", response_model=InternalSubscribersResponse)
async def list_topic_subscribers(
    topic_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    conn: asyncpg.Connection = Depends(get_connection),
    service: SubscriptionsService = Depends(get_subscriptions_service),
) -> InternalSubscribersResponse:
    subscribers, next_cursor = await service.list_internal_subscribers(
        conn=conn,
        topic_id=topic_id,
        limit=limit,
        cursor=cursor,
    )
    return InternalSubscribersResponse(
        items=[
            InternalSubscribersResponseItem(
                user_id=str(row.user_id),
                subscription_id=str(row.subscription_id),
                channels=row.channels,
                quiet_hours_start=row.quiet_hours_start,
                quiet_hours_end=row.quiet_hours_end,
                timezone=row.timezone,
            )
            for row in subscribers
        ],
        next_cursor=next_cursor,
    )
