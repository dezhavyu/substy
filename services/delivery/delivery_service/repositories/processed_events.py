from uuid import UUID

import asyncpg


class ProcessedEventsRepository:
    async def try_mark_processed(self, conn: asyncpg.Connection, event_id: UUID, subject: str) -> bool:
        try:
            await conn.execute(
                """
                INSERT INTO delivery.processed_events (event_id, subject)
                VALUES ($1, $2)
                """,
                event_id,
                subject,
            )
            return True
        except asyncpg.PostgresError as exc:
            if exc.sqlstate == "23505":
                return False
            raise
