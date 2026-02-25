from uuid import UUID

import asyncpg

from notifications_service.repositories.records import OutboxEventRecord


class OutboxRepository:
    async def create_event(
        self,
        conn: asyncpg.Connection,
        event_id: UUID,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict,
        headers: dict,
    ) -> OutboxEventRecord:
        row = await conn.fetchrow(
            """
            INSERT INTO notifications.outbox_events (
                id, aggregate_type, aggregate_id, event_type, payload, headers
            ) VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
            RETURNING id, aggregate_type, aggregate_id, event_type, payload, headers,
                      created_at, published_at, publish_attempts, last_error
            """,
            event_id,
            aggregate_type,
            aggregate_id,
            event_type,
            payload,
            headers,
        )
        return self._to_model(row)

    async def lock_unpublished_batch(
        self,
        conn: asyncpg.Connection,
        batch_size: int,
    ) -> list[OutboxEventRecord]:
        rows = await conn.fetch(
            """
            SELECT id, aggregate_type, aggregate_id, event_type, payload, headers,
                   created_at, published_at, publish_attempts, last_error
            FROM notifications.outbox_events
            WHERE published_at IS NULL
            ORDER BY created_at ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
            """,
            batch_size,
        )
        return [self._to_model(row) for row in rows]

    async def mark_published(self, conn: asyncpg.Connection, event_id: UUID) -> None:
        await conn.execute(
            """
            UPDATE notifications.outbox_events
            SET published_at = now(),
                publish_attempts = publish_attempts + 1,
                last_error = NULL
            WHERE id = $1
            """,
            event_id,
        )

    async def mark_failed(self, conn: asyncpg.Connection, event_id: UUID, error_message: str) -> None:
        await conn.execute(
            """
            UPDATE notifications.outbox_events
            SET publish_attempts = publish_attempts + 1,
                last_error = $2
            WHERE id = $1
            """,
            event_id,
            error_message[:2000],
        )

    async def count_unpublished(self, conn: asyncpg.Connection) -> int:
        count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM notifications.outbox_events
            WHERE published_at IS NULL
            """
        )
        return int(count)

    @staticmethod
    def _to_model(row: asyncpg.Record) -> OutboxEventRecord:
        return OutboxEventRecord(
            id=row["id"],
            aggregate_type=row["aggregate_type"],
            aggregate_id=row["aggregate_id"],
            event_type=row["event_type"],
            payload=dict(row["payload"]),
            headers=dict(row["headers"]),
            created_at=row["created_at"],
            published_at=row["published_at"],
            publish_attempts=row["publish_attempts"],
            last_error=row["last_error"],
        )
