from datetime import datetime
from uuid import UUID

import asyncpg

from subscriptions_service.core.exceptions import ConflictError
from subscriptions_service.repositories.records import TopicRecord


class TopicsRepository:
    async def create(
        self,
        conn: asyncpg.Connection,
        topic_id: UUID,
        key: str,
        name: str,
        description: str | None,
    ) -> TopicRecord:
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO subscriptions.topics (id, key, name, description)
                VALUES ($1, $2, $3, $4)
                RETURNING id, key, name, description, created_at
                """,
                topic_id,
                key,
                name,
                description,
            )
        except asyncpg.PostgresError as exc:
            if exc.sqlstate == "23505":
                raise ConflictError("Topic key already exists") from exc
            raise

        return self._to_topic(row)

    async def get_by_id(self, conn: asyncpg.Connection, topic_id: UUID) -> TopicRecord | None:
        row = await conn.fetchrow(
            """
            SELECT id, key, name, description, created_at
            FROM subscriptions.topics
            WHERE id = $1
            """,
            topic_id,
        )
        return self._to_topic(row) if row else None

    async def list_topics(
        self,
        conn: asyncpg.Connection,
        q: str | None,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: UUID | None,
    ) -> list[TopicRecord]:
        if cursor_created_at and cursor_id:
            rows = await conn.fetch(
                """
                SELECT id, key, name, description, created_at
                FROM subscriptions.topics
                WHERE (
                    $1::text IS NULL OR key ILIKE '%' || $1 || '%' OR name ILIKE '%' || $1 || '%'
                )
                  AND (created_at, id) < ($2, $3)
                ORDER BY created_at DESC, id DESC
                LIMIT $4
                """,
                q,
                cursor_created_at,
                cursor_id,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, key, name, description, created_at
                FROM subscriptions.topics
                WHERE ($1::text IS NULL OR key ILIKE '%' || $1 || '%' OR name ILIKE '%' || $1 || '%')
                ORDER BY created_at DESC, id DESC
                LIMIT $2
                """,
                q,
                limit,
            )

        return [self._to_topic(row) for row in rows]

    @staticmethod
    def _to_topic(row: asyncpg.Record) -> TopicRecord:
        return TopicRecord(
            id=row["id"],
            key=row["key"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
        )
