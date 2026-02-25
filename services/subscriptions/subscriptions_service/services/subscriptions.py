from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from subscriptions_service.core.exceptions import NotFoundError, ValidationError
from subscriptions_service.core.pagination import decode_cursor, subscribers_cursor, subscriptions_cursor
from subscriptions_service.repositories.records import SubscriberRecord, SubscriptionRecord
from subscriptions_service.repositories.subscriptions import SubscriptionsRepository
from subscriptions_service.repositories.topics import TopicsRepository


class SubscriptionsService:
    def __init__(
        self,
        subscriptions_repository: SubscriptionsRepository,
        topics_repository: TopicsRepository,
    ) -> None:
        self._subscriptions = subscriptions_repository
        self._topics = topics_repository

    async def list_my(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[SubscriptionRecord], str | None]:
        cursor_data = decode_cursor(cursor)

        created_at: datetime | None = None
        subscription_id: UUID | None = None
        if cursor_data:
            try:
                created_at = datetime.fromisoformat(cursor_data["created_at"])
                subscription_id = UUID(cursor_data["id"])
            except (ValueError, KeyError) as exc:
                raise ValidationError("Invalid cursor") from exc

        rows = await self._subscriptions.list_for_user(
            conn=conn,
            user_id=user_id,
            limit=limit + 1,
            cursor_created_at=created_at,
            cursor_id=subscription_id,
        )

        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = subscriptions_cursor(last.created_at, last.id)

        return rows, next_cursor

    async def subscribe(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        topic_id: UUID,
    ) -> tuple[SubscriptionRecord, bool]:
        topic = await self._topics.get_by_id(conn, topic_id)
        if topic is None:
            raise NotFoundError("Topic not found")

        existing = await self._subscriptions.get_by_user_topic(conn, user_id=user_id, topic_id=topic_id)
        if existing:
            if existing.is_active:
                return existing, False

            updated = await self._subscriptions.update_active(
                conn,
                subscription_id=existing.id,
                user_id=user_id,
                is_active=True,
            )
            if updated is None:
                raise NotFoundError("Subscription not found")
            return updated, False

        created = await self._subscriptions.create(
            conn,
            subscription_id=uuid4(),
            user_id=user_id,
            topic_id=topic_id,
        )
        return created, True

    async def unsubscribe(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        subscription_id: UUID,
    ) -> None:
        # Soft delete is used to preserve history and avoid race conditions during fan-out processing.
        existing = await self._subscriptions.get_by_id_for_user(conn, subscription_id, user_id)
        if existing is None:
            raise NotFoundError("Subscription not found")

        if existing.is_active:
            await self._subscriptions.update_active(
                conn,
                subscription_id=subscription_id,
                user_id=user_id,
                is_active=False,
            )

    async def update_status(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        subscription_id: UUID,
        is_active: bool,
    ) -> SubscriptionRecord:
        updated = await self._subscriptions.update_active(
            conn,
            subscription_id=subscription_id,
            user_id=user_id,
            is_active=is_active,
        )
        if updated is None:
            raise NotFoundError("Subscription not found")
        return updated

    async def list_internal_subscribers(
        self,
        conn: asyncpg.Connection,
        topic_id: UUID,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[SubscriberRecord], str | None]:
        topic = await self._topics.get_by_id(conn, topic_id)
        if topic is None:
            raise NotFoundError("Topic not found")

        cursor_data = decode_cursor(cursor)
        cursor_user_id: UUID | None = None
        cursor_subscription_id: UUID | None = None
        if cursor_data:
            try:
                cursor_user_id = UUID(cursor_data["user_id"])
                cursor_subscription_id = UUID(cursor_data["id"])
            except (ValueError, KeyError) as exc:
                raise ValidationError("Invalid cursor") from exc

        rows = await self._subscriptions.list_active_subscribers(
            conn=conn,
            topic_id=topic_id,
            limit=limit + 1,
            cursor_user_id=cursor_user_id,
            cursor_subscription_id=cursor_subscription_id,
        )

        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = subscribers_cursor(last.user_id, last.subscription_id)

        return rows, next_cursor
