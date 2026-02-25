from datetime import datetime, timezone
from uuid import uuid4

import pytest

from notifications_service.core.exceptions import ForbiddenError
from notifications_service.core.metrics import MetricsRegistry
from notifications_service.core.settings import Settings
from notifications_service.repositories.records import NotificationRecord
from notifications_service.services.notifications import NotificationsService


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def transaction(self):
        return FakeTransaction()


class FakeNotificationsRepo:
    def __init__(self) -> None:
        self.rows: dict[str, NotificationRecord] = {}

    async def create(self, conn, notification_id, topic_id, payload, scheduled_at, created_by, idempotency_key):
        row = NotificationRecord(
            id=notification_id,
            topic_id=topic_id,
            payload=payload,
            scheduled_at=scheduled_at,
            status="created",
            created_by=created_by,
            idempotency_key=idempotency_key,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.rows[str(notification_id)] = row
        return row

    async def get_by_id(self, conn, notification_id):
        return self.rows.get(str(notification_id))

    async def get_by_idempotency_key(self, conn, created_by, idempotency_key):
        for row in self.rows.values():
            if row.created_by == created_by and row.idempotency_key == idempotency_key:
                return row
        return None

    async def list_by_user(self, conn, created_by, limit, cursor_created_at, cursor_id, status, topic_id):
        rows = [x for x in self.rows.values() if x.created_by == created_by]
        rows.sort(key=lambda x: (x.created_at, x.id), reverse=True)
        return rows[:limit]


class FakeOutboxRepo:
    async def create_event(self, conn, event_id, aggregate_type, aggregate_id, event_type, payload, headers):
        return None


@pytest.mark.asyncio
async def test_idempotent_create_by_user_and_key():
    service = NotificationsService(
        notifications_repository=FakeNotificationsRepo(),
        outbox_repository=FakeOutboxRepo(),
        settings=Settings(),
        metrics=MetricsRegistry(),
    )

    user_id = uuid4()
    topic_id = uuid4()

    conn = FakeConnection()

    first, first_created = await service.create_notification(
        conn=conn,
        user_id=user_id,
        topic_id=topic_id,
        payload={"x": 1},
        scheduled_at=None,
        idempotency_key="same-key",
        request_id="req-1",
    )
    second, second_created = await service.create_notification(
        conn=conn,
        user_id=user_id,
        topic_id=topic_id,
        payload={"x": 2},
        scheduled_at=None,
        idempotency_key="same-key",
        request_id="req-2",
    )

    assert first_created is True
    assert second_created is False
    assert first.id == second.id


@pytest.mark.asyncio
async def test_forbid_reading_foreign_notification_without_admin():
    repo = FakeNotificationsRepo()
    service = NotificationsService(
        notifications_repository=repo,
        outbox_repository=FakeOutboxRepo(),
        settings=Settings(),
        metrics=MetricsRegistry(),
    )

    owner = uuid4()
    notification = await repo.create(
        None,
        notification_id=uuid4(),
        topic_id=uuid4(),
        payload={"x": 1},
        scheduled_at=None,
        created_by=owner,
        idempotency_key=None,
    )

    with pytest.raises(ForbiddenError):
        await service.get_notification(
            conn=None,
            notification_id=notification.id,
            user_id=uuid4(),
            roles={"user"},
        )
