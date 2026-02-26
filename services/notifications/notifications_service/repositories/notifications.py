import json
from datetime import datetime
from uuid import UUID

import asyncpg

from notifications_service.repositories.records import NotificationRecord


class NotificationsRepository:
    async def create(
        self,
        conn: asyncpg.Connection,
        notification_id: UUID,
        topic_id: UUID,
        payload: dict,
        scheduled_at: datetime | None,
        created_by: UUID,
        idempotency_key: str | None,
        status: str,
    ) -> NotificationRecord:
        row = await conn.fetchrow(
            """
            INSERT INTO notifications.notifications (
                id, topic_id, payload, scheduled_at, status, created_by, idempotency_key
            ) VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7)
            RETURNING id, topic_id, payload, scheduled_at, status, created_by, idempotency_key, created_at, updated_at
            """,
            notification_id,
            topic_id,
            json.dumps(payload, separators=(",", ":")),
            scheduled_at,
            status,
            created_by,
            idempotency_key,
        )
        return self._to_model(row)

    async def get_by_id(self, conn: asyncpg.Connection, notification_id: UUID) -> NotificationRecord | None:
        row = await conn.fetchrow(
            """
            SELECT id, topic_id, payload, scheduled_at, status, created_by, idempotency_key, created_at, updated_at
            FROM notifications.notifications
            WHERE id = $1
            """,
            notification_id,
        )
        return self._to_model(row) if row else None

    async def get_by_idempotency_key(
        self,
        conn: asyncpg.Connection,
        created_by: UUID,
        idempotency_key: str,
    ) -> NotificationRecord | None:
        row = await conn.fetchrow(
            """
            SELECT id, topic_id, payload, scheduled_at, status, created_by, idempotency_key, created_at, updated_at
            FROM notifications.notifications
            WHERE created_by = $1
              AND idempotency_key = $2
            """,
            created_by,
            idempotency_key,
        )
        return self._to_model(row) if row else None

    async def list_by_user(
        self,
        conn: asyncpg.Connection,
        created_by: UUID,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
        status: str | None,
        topic_id: UUID | None,
    ) -> list[NotificationRecord]:
        filters = ["created_by = $1"]
        params: list = [created_by]
        idx = 2

        if status is not None:
            filters.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        if topic_id is not None:
            filters.append(f"topic_id = ${idx}")
            params.append(topic_id)
            idx += 1

        if cursor_created_at is not None and cursor_id is not None:
            filters.append(f"(created_at, id) < (${idx}, ${idx + 1})")
            params.extend([cursor_created_at, cursor_id])
            idx += 2

        where_clause = " AND ".join(filters)
        query = f"""
            SELECT id, topic_id, payload, scheduled_at, status, created_by, idempotency_key, created_at, updated_at
            FROM notifications.notifications
            WHERE {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ${idx}
        """
        params.append(limit)

        rows = await conn.fetch(query, *params)
        return [self._to_model(row) for row in rows]

    async def lock_due_scheduled_batch(
        self,
        conn: asyncpg.Connection,
        limit: int,
    ) -> list[NotificationRecord]:
        rows = await conn.fetch(
            """
            SELECT id, topic_id, payload, scheduled_at, status, created_by, idempotency_key, created_at, updated_at
            FROM notifications.notifications
            WHERE status = 'scheduled'
              AND scheduled_at <= now()
            ORDER BY scheduled_at ASC, id ASC
            LIMIT $1
            FOR UPDATE SKIP LOCKED
            """,
            limit,
        )
        return [self._to_model(row) for row in rows]

    async def mark_queued_by_ids(
        self,
        conn: asyncpg.Connection,
        notification_ids: list[UUID],
    ) -> list[NotificationRecord]:
        if not notification_ids:
            return []

        rows = await conn.fetch(
            """
            WITH updated AS (
                UPDATE notifications.notifications
                SET status = 'queued',
                    updated_at = now()
                WHERE id = ANY($1::uuid[])
                  AND status = 'scheduled'
                RETURNING id, topic_id, payload, scheduled_at, status, created_by, idempotency_key, created_at, updated_at
            )
            SELECT id, topic_id, payload, scheduled_at, status, created_by, idempotency_key, created_at, updated_at
            FROM updated
            ORDER BY scheduled_at ASC, id ASC
            """,
            notification_ids,
        )
        return [self._to_model(row) for row in rows]

    async def cancel_if_scheduled(
        self,
        conn: asyncpg.Connection,
        notification_id: UUID,
    ) -> NotificationRecord | None:
        row = await conn.fetchrow(
            """
            UPDATE notifications.notifications
            SET status = 'cancelled',
                updated_at = now()
            WHERE id = $1
              AND status = 'scheduled'
            RETURNING id, topic_id, payload, scheduled_at, status, created_by, idempotency_key, created_at, updated_at
            """,
            notification_id,
        )
        return self._to_model(row) if row else None

    async def count_scheduled_backlog(self, conn: asyncpg.Connection) -> int:
        count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM notifications.notifications
            WHERE status = 'scheduled'
            """
        )
        return int(count)

    async def count_scheduled_due(self, conn: asyncpg.Connection) -> int:
        count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM notifications.notifications
            WHERE status = 'scheduled'
              AND scheduled_at <= now()
            """
        )
        return int(count)

    @staticmethod
    def _to_model(row: asyncpg.Record) -> NotificationRecord:
        raw_payload = row["payload"]
        if isinstance(raw_payload, str):
            payload = json.loads(raw_payload)
        elif isinstance(raw_payload, dict):
            payload = raw_payload
        else:
            payload = dict(raw_payload)

        return NotificationRecord(
            id=row["id"],
            topic_id=row["topic_id"],
            payload=payload,
            scheduled_at=row["scheduled_at"],
            status=row["status"],
            created_by=row["created_by"],
            idempotency_key=row["idempotency_key"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
