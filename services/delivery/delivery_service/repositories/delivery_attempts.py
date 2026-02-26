import json
from datetime import datetime, time
from uuid import UUID

import asyncpg

from delivery_service.repositories.records import DeliveryAttemptRecord


class DeliveryAttemptsRepository:
    async def create_or_get(
        self,
        conn: asyncpg.Connection,
        attempt_id: UUID,
        notification_id: UUID,
        user_id: UUID,
        channel: str,
        payload: dict,
        quiet_hours_start: time | None,
        quiet_hours_end: time | None,
        timezone: str,
    ) -> tuple[DeliveryAttemptRecord, bool]:
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO delivery.delivery_attempts (
                    id,
                    notification_id,
                    user_id,
                    channel,
                    payload,
                    quiet_hours_start,
                    quiet_hours_end,
                    timezone,
                    status,
                    attempt_no
                ) VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, 'pending', 0)
                RETURNING id, notification_id, user_id, channel, payload,
                          quiet_hours_start, quiet_hours_end, timezone,
                          status, attempt_no,
                          last_error_code, last_error_message, next_retry_at, created_at, updated_at
                """,
                attempt_id,
                notification_id,
                user_id,
                channel,
                json.dumps(payload, separators=(",", ":")),
                quiet_hours_start,
                quiet_hours_end,
                timezone,
            )
            return self._to_record(row), True
        except asyncpg.PostgresError as exc:
            if exc.sqlstate != "23505":
                raise
            row = await conn.fetchrow(
                """
                SELECT id, notification_id, user_id, channel, payload,
                       quiet_hours_start, quiet_hours_end, timezone,
                       status, attempt_no,
                       last_error_code, last_error_message, next_retry_at, created_at, updated_at
                FROM delivery.delivery_attempts
                WHERE notification_id = $1
                  AND user_id = $2
                  AND channel = $3
                """,
                notification_id,
                user_id,
                channel,
            )
            return self._to_record(row), False

    async def get_for_update(self, conn: asyncpg.Connection, attempt_id: UUID) -> DeliveryAttemptRecord | None:
        row = await conn.fetchrow(
            """
            SELECT id, notification_id, user_id, channel, payload,
                   quiet_hours_start, quiet_hours_end, timezone,
                   status, attempt_no,
                   last_error_code, last_error_message, next_retry_at, created_at, updated_at
            FROM delivery.delivery_attempts
            WHERE id = $1
            FOR UPDATE
            """,
            attempt_id,
        )
        return self._to_record(row) if row else None

    async def mark_sent(self, conn: asyncpg.Connection, attempt_id: UUID) -> None:
        await conn.execute(
            """
            UPDATE delivery.delivery_attempts
            SET status = 'sent',
                updated_at = now(),
                next_retry_at = NULL,
                last_error_code = NULL,
                last_error_message = NULL
            WHERE id = $1
            """,
            attempt_id,
        )

    async def mark_delayed(
        self,
        conn: asyncpg.Connection,
        attempt_id: UUID,
        next_retry_at: datetime,
        error_code: str,
        error_message: str,
    ) -> None:
        await conn.execute(
            """
            UPDATE delivery.delivery_attempts
            SET status = 'failed',
                last_error_code = $2,
                last_error_message = $3,
                next_retry_at = $4,
                updated_at = now()
            WHERE id = $1
            """,
            attempt_id,
            error_code,
            error_message[:512],
            next_retry_at,
        )

    async def mark_failed(
        self,
        conn: asyncpg.Connection,
        attempt_id: UUID,
        attempt_no: int,
        error_code: str,
        error_message: str,
        next_retry_at: datetime | None,
        dead: bool,
    ) -> None:
        status = "dead" if dead else "failed"
        await conn.execute(
            """
            UPDATE delivery.delivery_attempts
            SET status = $2,
                attempt_no = $3,
                last_error_code = $4,
                last_error_message = $5,
                next_retry_at = $6,
                updated_at = now()
            WHERE id = $1
            """,
            attempt_id,
            status,
            attempt_no,
            error_code,
            error_message[:512],
            next_retry_at,
        )

    @staticmethod
    def _to_record(row: asyncpg.Record) -> DeliveryAttemptRecord:
        raw_payload = row["payload"]
        if isinstance(raw_payload, str):
            payload = json.loads(raw_payload)
        elif isinstance(raw_payload, dict):
            payload = raw_payload
        else:
            payload = dict(raw_payload)

        return DeliveryAttemptRecord(
            id=row["id"],
            notification_id=row["notification_id"],
            user_id=row["user_id"],
            channel=row["channel"],
            payload=payload,
            quiet_hours_start=row["quiet_hours_start"],
            quiet_hours_end=row["quiet_hours_end"],
            timezone=row["timezone"],
            status=row["status"],
            attempt_no=row["attempt_no"],
            last_error_code=row["last_error_code"],
            last_error_message=row["last_error_message"],
            next_retry_at=row["next_retry_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
