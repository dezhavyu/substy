from datetime import datetime
from uuid import UUID

import asyncpg

from subscriptions_service.repositories.records import SubscriberRecord, SubscriptionRecord


class SubscriptionsRepository:
    async def create(
        self,
        conn: asyncpg.Connection,
        subscription_id: UUID,
        user_id: UUID,
        topic_id: UUID,
    ) -> SubscriptionRecord:
        row = await conn.fetchrow(
            """
            INSERT INTO subscriptions.subscriptions (id, user_id, topic_id, is_active)
            VALUES ($1, $2, $3, TRUE)
            RETURNING id, user_id, topic_id, is_active, created_at, updated_at
            """,
            subscription_id,
            user_id,
            topic_id,
        )
        return self._to_subscription(row)

    async def get_by_user_topic(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        topic_id: UUID,
    ) -> SubscriptionRecord | None:
        row = await conn.fetchrow(
            """
            SELECT id, user_id, topic_id, is_active, created_at, updated_at
            FROM subscriptions.subscriptions
            WHERE user_id = $1 AND topic_id = $2
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
            """
            SELECT id, user_id, topic_id, is_active, created_at, updated_at
            FROM subscriptions.subscriptions
            WHERE id = $1 AND user_id = $2
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
                """
                SELECT id, user_id, topic_id, is_active, created_at, updated_at
                FROM subscriptions.subscriptions
                WHERE user_id = $1
                  AND (created_at, id) < ($2, $3)
                ORDER BY created_at DESC, id DESC
                LIMIT $4
                """,
                user_id,
                cursor_created_at,
                cursor_id,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, user_id, topic_id, is_active, created_at, updated_at
                FROM subscriptions.subscriptions
                WHERE user_id = $1
                ORDER BY created_at DESC, id DESC
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
        row = await conn.fetchrow(
            """
            UPDATE subscriptions.subscriptions
            SET is_active = $3,
                updated_at = now()
            WHERE id = $1 AND user_id = $2
            RETURNING id, user_id, topic_id, is_active, created_at, updated_at
            """,
            subscription_id,
            user_id,
            is_active,
        )
        return self._to_subscription(row) if row else None

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
                SELECT user_id, id
                FROM subscriptions.subscriptions
                WHERE topic_id = $1
                  AND is_active = TRUE
                  AND (user_id, id) > ($2, $3)
                ORDER BY user_id ASC, id ASC
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
                SELECT user_id, id
                FROM subscriptions.subscriptions
                WHERE topic_id = $1
                  AND is_active = TRUE
                ORDER BY user_id ASC, id ASC
                LIMIT $2
                """,
                topic_id,
                limit,
            )

        return [SubscriberRecord(user_id=row["user_id"], subscription_id=row["id"]) for row in rows]

    @staticmethod
    def _to_subscription(row: asyncpg.Record) -> SubscriptionRecord:
        return SubscriptionRecord(
            id=row["id"],
            user_id=row["user_id"],
            topic_id=row["topic_id"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
