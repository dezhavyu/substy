from datetime import datetime, time
from uuid import UUID

import asyncpg

from subscriptions_service.repositories.records import (
    SubscriberRecord,
    SubscriptionPreferencesRecord,
    SubscriptionRecord,
)


DEFAULT_CHANNELS = ["push"]
DEFAULT_TIMEZONE = "UTC"


class SubscriptionsRepository:
    _subscription_select = """
        SELECT
            s.id,
            s.user_id,
            s.topic_id,
            s.is_active,
            s.created_at,
            s.updated_at,
            COALESCE(p.channels, ARRAY['push']::text[]) AS pref_channels,
            p.quiet_hours_start AS pref_quiet_hours_start,
            p.quiet_hours_end AS pref_quiet_hours_end,
            COALESCE(p.timezone, 'UTC') AS pref_timezone,
            COALESCE(p.updated_at, s.updated_at) AS pref_updated_at
        FROM subscriptions.subscriptions s
        LEFT JOIN subscriptions.subscription_preferences p
          ON p.subscription_id = s.id
    """

    async def create(
        self,
        conn: asyncpg.Connection,
        subscription_id: UUID,
        user_id: UUID,
        topic_id: UUID,
    ) -> SubscriptionRecord:
        await conn.execute(
            """
            INSERT INTO subscriptions.subscriptions (id, user_id, topic_id, is_active)
            VALUES ($1, $2, $3, TRUE)
            """,
            subscription_id,
            user_id,
            topic_id,
        )
        await self.upsert_preferences(
            conn=conn,
            subscription_id=subscription_id,
            channels=DEFAULT_CHANNELS,
            quiet_hours_start=None,
            quiet_hours_end=None,
            timezone=DEFAULT_TIMEZONE,
        )

        created = await self.get_by_id_for_user(
            conn=conn,
            subscription_id=subscription_id,
            user_id=user_id,
        )
        if created is None:
            raise RuntimeError("Failed to fetch created subscription")
        return created

    async def get_by_user_topic(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        topic_id: UUID,
    ) -> SubscriptionRecord | None:
        row = await conn.fetchrow(
            f"""
            {self._subscription_select}
            WHERE s.user_id = $1 AND s.topic_id = $2
            """,
            user_id,
            topic_id,
        )
        return self._to_subscription(row) if row else None

    async def get_by_id_for_user(
        self,
        conn: asyncpg.Connection,
        subscription_id: UUID,
        user_id: UUID,
    ) -> SubscriptionRecord | None:
        row = await conn.fetchrow(
            f"""
            {self._subscription_select}
            WHERE s.id = $1 AND s.user_id = $2
            """,
            subscription_id,
            user_id,
        )
        return self._to_subscription(row) if row else None

    async def list_for_user(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> list[SubscriptionRecord]:
        if cursor_created_at and cursor_id:
            rows = await conn.fetch(
                f"""
                {self._subscription_select}
                WHERE s.user_id = $1
                  AND (s.created_at, s.id) < ($2, $3)
                ORDER BY s.created_at DESC, s.id DESC
                LIMIT $4
                """,
                user_id,
                cursor_created_at,
                cursor_id,
                limit,
            )
        else:
            rows = await conn.fetch(
                f"""
                {self._subscription_select}
                WHERE s.user_id = $1
                ORDER BY s.created_at DESC, s.id DESC
                LIMIT $2
                """,
                user_id,
                limit,
            )

        return [self._to_subscription(row) for row in rows]

    async def update_active(
        self,
        conn: asyncpg.Connection,
        subscription_id: UUID,
        user_id: UUID,
        is_active: bool,
    ) -> SubscriptionRecord | None:
        updated_id = await conn.fetchval(
            """
            UPDATE subscriptions.subscriptions
            SET is_active = $3,
                updated_at = now()
            WHERE id = $1 AND user_id = $2
            RETURNING id
            """,
            subscription_id,
            user_id,
            is_active,
        )
        if updated_id is None:
            return None

        return await self.get_by_id_for_user(conn, subscription_id, user_id)

    async def upsert_preferences(
        self,
        conn: asyncpg.Connection,
        subscription_id: UUID,
        channels: list[str],
        quiet_hours_start: time | None,
        quiet_hours_end: time | None,
        timezone: str,
    ) -> None:
        await conn.execute(
            """
            INSERT INTO subscriptions.subscription_preferences (
                subscription_id,
                channels,
                quiet_hours_start,
                quiet_hours_end,
                timezone,
                updated_at
            ) VALUES ($1, $2::text[], $3, $4, $5, now())
            ON CONFLICT (subscription_id) DO UPDATE
            SET channels = EXCLUDED.channels,
                quiet_hours_start = EXCLUDED.quiet_hours_start,
                quiet_hours_end = EXCLUDED.quiet_hours_end,
                timezone = EXCLUDED.timezone,
                updated_at = now()
            """,
            subscription_id,
            channels,
            quiet_hours_start,
            quiet_hours_end,
            timezone,
        )

    async def list_active_subscribers(
        self,
        conn: asyncpg.Connection,
        topic_id: UUID,
        limit: int,
        cursor_user_id: UUID | None,
        cursor_subscription_id: UUID | None,
    ) -> list[SubscriberRecord]:
        if cursor_user_id and cursor_subscription_id:
            rows = await conn.fetch(
                """
                SELECT
                    s.user_id,
                    s.id AS subscription_id,
                    COALESCE(p.channels, ARRAY['push']::text[]) AS channels,
                    p.quiet_hours_start,
                    p.quiet_hours_end,
                    COALESCE(p.timezone, 'UTC') AS timezone
                FROM subscriptions.subscriptions s
                LEFT JOIN subscriptions.subscription_preferences p
                  ON p.subscription_id = s.id
                WHERE s.topic_id = $1
                  AND s.is_active = TRUE
                  AND (s.user_id, s.id) > ($2, $3)
                ORDER BY s.user_id ASC, s.id ASC
                LIMIT $4
                """,
                topic_id,
                cursor_user_id,
                cursor_subscription_id,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    s.user_id,
                    s.id AS subscription_id,
                    COALESCE(p.channels, ARRAY['push']::text[]) AS channels,
                    p.quiet_hours_start,
                    p.quiet_hours_end,
                    COALESCE(p.timezone, 'UTC') AS timezone
                FROM subscriptions.subscriptions s
                LEFT JOIN subscriptions.subscription_preferences p
                  ON p.subscription_id = s.id
                WHERE s.topic_id = $1
                  AND s.is_active = TRUE
                ORDER BY s.user_id ASC, s.id ASC
                LIMIT $2
                """,
                topic_id,
                limit,
            )

        return [
            SubscriberRecord(
                user_id=row["user_id"],
                subscription_id=row["subscription_id"],
                channels=list(row["channels"]),
                quiet_hours_start=row["quiet_hours_start"],
                quiet_hours_end=row["quiet_hours_end"],
                timezone=row["timezone"],
            )
            for row in rows
        ]

    @staticmethod
    def _to_subscription(row: asyncpg.Record) -> SubscriptionRecord:
        return SubscriptionRecord(
            id=row["id"],
            user_id=row["user_id"],
            topic_id=row["topic_id"],
            is_active=row["is_active"],
            preferences=SubscriptionPreferencesRecord(
                channels=list(row["pref_channels"]),
                quiet_hours_start=row["pref_quiet_hours_start"],
                quiet_hours_end=row["pref_quiet_hours_end"],
                timezone=row["pref_timezone"],
                updated_at=row["pref_updated_at"],
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
