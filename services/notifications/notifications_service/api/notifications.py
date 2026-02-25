from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, Response, status

from notifications_service.api.dependencies import get_notifications_service
from notifications_service.core.dependencies import (
    get_connection,
    get_current_user_id,
    get_request_id,
    get_roles,
)
from notifications_service.schemas.notifications import (
    CreateNotificationRequest,
    ListNotificationsResponse,
    NotificationResponse,
)
from notifications_service.services.notifications import NotificationsService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    payload: CreateNotificationRequest,
    response: Response,
    user_id: UUID = Depends(get_current_user_id),
    request_id: str = Depends(get_request_id),
    conn: asyncpg.Connection = Depends(get_connection),
    service: NotificationsService = Depends(get_notifications_service),
) -> NotificationResponse:
    notification, created = await service.create_notification(
        conn=conn,
        user_id=user_id,
        topic_id=payload.topic_id,
        payload=payload.payload,
        scheduled_at=payload.scheduled_at,
        idempotency_key=payload.idempotency_key,
        request_id=request_id,
    )

    if not created:
        response.status_code = status.HTTP_200_OK

    return NotificationResponse(
        id=notification.id,
        topic_id=notification.topic_id,
        status=notification.status,
        scheduled_at=notification.scheduled_at,
        created_at=notification.created_at,
    )


@router.get("/me", response_model=ListNotificationsResponse)
async def list_my_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    topic_id: UUID | None = Query(default=None),
    user_id: UUID = Depends(get_current_user_id),
    conn: asyncpg.Connection = Depends(get_connection),
    service: NotificationsService = Depends(get_notifications_service),
) -> ListNotificationsResponse:
    rows, next_cursor = await service.list_my_notifications(
        conn=conn,
        user_id=user_id,
        limit=limit,
        cursor=cursor,
        status=status_filter,
        topic_id=topic_id,
    )
    return ListNotificationsResponse(
        items=[
            NotificationResponse(
                id=row.id,
                topic_id=row.topic_id,
                status=row.status,
                scheduled_at=row.scheduled_at,
                created_at=row.created_at,
            )
            for row in rows
        ],
        next_cursor=next_cursor,
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    roles: set[str] = Depends(get_roles),
    conn: asyncpg.Connection = Depends(get_connection),
    service: NotificationsService = Depends(get_notifications_service),
) -> NotificationResponse:
    notification = await service.get_notification(
        conn=conn,
        notification_id=notification_id,
        user_id=user_id,
        roles=roles,
    )
    return NotificationResponse(
        id=notification.id,
        topic_id=notification.topic_id,
        status=notification.status,
        scheduled_at=notification.scheduled_at,
        created_at=notification.created_at,
    )
