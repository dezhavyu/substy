from datetime import datetime, time
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import asyncpg

from subscriptions_service.core.exceptions import NotFoundError, ValidationError
from subscriptions_service.core.pagination import decode_cursor, subscribers_cursor, subscriptions_cursor
from subscriptions_service.repositories.records import SubscriberRecord, SubscriptionRecord
from subscriptions_service.repositories.subscriptions import SubscriptionsRepository
from subscriptions_service.repositories.topics import TopicsRepository
from subscriptions_service.schemas.subscriptions import SubscriptionPreferencesPatchRequest


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

        async with conn.transaction():
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

    async def update_subscription(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        subscription_id: UUID,
        is_active: bool | None,
        preferences_patch: SubscriptionPreferencesPatchRequest | None,
    ) -> SubscriptionRecord:
        existing = await self._subscriptions.get_by_id_for_user(
            conn=conn,
            subscription_id=subscription_id,
            user_id=user_id,
        )
        if existing is None:
            raise NotFoundError("Subscription not found")

        target_is_active = existing.is_active if is_active is None else is_active
        target_channels = existing.preferences.channels
        target_timezone = existing.preferences.timezone
        target_quiet_start = existing.preferences.quiet_hours_start
        target_quiet_end = existing.preferences.quiet_hours_end

        if preferences_patch is not None:
            if preferences_patch.channels is not None:
                target_channels = self._normalize_channels(preferences_patch.channels)

            if preferences_patch.timezone is not None:
                target_timezone = self._validate_timezone(preferences_patch.timezone)

            if preferences_patch.quiet_hours is not None:
                start = preferences_patch.quiet_hours.start
                end = preferences_patch.quiet_hours.end
                if start == end:
                    target_quiet_start = None
                    target_quiet_end = None
                else:
                    target_quiet_start = start
                    target_quiet_end = end

        if (target_quiet_start is None) ^ (target_quiet_end is None):
            raise ValidationError("quiet hours must include both start and end")

        async with conn.transaction():
            if target_is_active != existing.is_active:
                updated = await self._subscriptions.update_active(
                    conn=conn,
                    subscription_id=subscription_id,
                    user_id=user_id,
                    is_active=target_is_active,
                )
                if updated is None:
                    raise NotFoundError("Subscription not found")

            if preferences_patch is not None:
                await self._subscriptions.upsert_preferences(
                    conn=conn,
                    subscription_id=subscription_id,
                    channels=target_channels,
                    quiet_hours_start=target_quiet_start,
                    quiet_hours_end=target_quiet_end,
                    timezone=target_timezone,
                )

            current = await self._subscriptions.get_by_id_for_user(
                conn=conn,
                subscription_id=subscription_id,
                user_id=user_id,
            )

        if current is None:
            raise NotFoundError("Subscription not found")
        return current

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

    @staticmethod
    def _normalize_channels(channels: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for channel in channels:
            lowered = channel.strip().lower()
            if lowered and lowered not in seen:
                seen.add(lowered)
                normalized.append(lowered)

        if not normalized:
            raise ValidationError("channels must not be empty")
        return normalized

    @staticmethod
    def _validate_timezone(timezone_name: str) -> str:
        timezone_name = timezone_name.strip()
        if not timezone_name:
            raise ValidationError("timezone must not be empty")

        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValidationError("Invalid timezone") from exc

        return timezone_name
