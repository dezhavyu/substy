from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from subscriptions_service.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from subscriptions_service.core.pagination import decode_cursor, topic_cursor
from subscriptions_service.repositories.records import TopicRecord
from subscriptions_service.repositories.topics import TopicsRepository


class TopicsService:
    def __init__(self, topics_repository: TopicsRepository) -> None:
        self._topics = topics_repository

    async def create_topic(
        self,
        conn: asyncpg.Connection,
        roles: set[str],
        key: str,
        name: str,
        description: str | None,
    ) -> TopicRecord:
        if "admin" not in roles:
            raise ForbiddenError()

        return await self._topics.create(conn, topic_id=uuid4(), key=key, name=name, description=description)

    async def get_topic(self, conn: asyncpg.Connection, topic_id: UUID) -> TopicRecord:
        topic = await self._topics.get_by_id(conn, topic_id)
        if topic is None:
            raise NotFoundError("Topic not found")
        return topic

    async def list_topics(
        self,
        conn: asyncpg.Connection,
        q: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[TopicRecord], str | None]:
        cursor_data = decode_cursor(cursor)

        created_at: datetime | None = None
        topic_id: UUID | None = None
        if cursor_data:
            try:
                created_at = datetime.fromisoformat(cursor_data["created_at"])
                topic_id = UUID(cursor_data["id"])
            except (ValueError, KeyError) as exc:
                raise ValidationError("Invalid cursor") from exc

        rows = await self._topics.list_topics(
            conn=conn,
            q=q,
            limit=limit + 1,
            cursor_created_at=created_at,
            cursor_id=topic_id,
        )

        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = topic_cursor(last.created_at, last.id)

        return rows, next_cursor
