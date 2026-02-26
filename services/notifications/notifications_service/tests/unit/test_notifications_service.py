from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from notifications_service.core.exceptions import ConflictError, ForbiddenError
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

    async def create(self, conn, notification_id, topic_id, payload, scheduled_at, created_by, idempotency_key, status):
        now = datetime.now(timezone.utc)
        row = NotificationRecord(
            id=notification_id,
            topic_id=topic_id,
            payload=payload,
            scheduled_at=scheduled_at,
            status=status,
            created_by=created_by,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
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

    async def cancel_if_scheduled(self, conn, notification_id):
        row = self.rows.get(str(notification_id))
        if row is None or row.status != "scheduled":
            return None

        cancelled = NotificationRecord(
            id=row.id,
            topic_id=row.topic_id,
            payload=row.payload,
            scheduled_at=row.scheduled_at,
            status="cancelled",
            created_by=row.created_by,
            idempotency_key=row.idempotency_key,
            created_at=row.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self.rows[str(notification_id)] = cancelled
        return cancelled


class FakeOutboxRepo:
    def __init__(self) -> None:
        self.created_events: list[dict] = []

    async def create_event(self, conn, event_id, aggregate_type, aggregate_id, event_type, payload, headers):
        self.created_events.append(
            {
                "event_id": event_id,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "event_type": event_type,
                "payload": payload,
                "headers": headers,
            }
        )
        return None


@pytest.mark.asyncio
async def test_idempotent_create_by_user_and_key():
    notifications_repo = FakeNotificationsRepo()
    outbox_repo = FakeOutboxRepo()
    service = NotificationsService(
        notifications_repository=notifications_repo,
        outbox_repository=outbox_repo,
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
    assert len(outbox_repo.created_events) == 1


@pytest.mark.asyncio
async def test_future_scheduled_notification_is_not_written_to_outbox():
    notifications_repo = FakeNotificationsRepo()
    outbox_repo = FakeOutboxRepo()
    service = NotificationsService(
        notifications_repository=notifications_repo,
        outbox_repository=outbox_repo,
        settings=Settings(),
        metrics=MetricsRegistry(),
    )

    notification, created = await service.create_notification(
        conn=FakeConnection(),
        user_id=uuid4(),
        topic_id=uuid4(),
        payload={"title": "future"},
        scheduled_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        idempotency_key=None,
        request_id="req-scheduled",
    )

    assert created is True
    assert notification.status == "scheduled"
    assert len(outbox_repo.created_events) == 0


@pytest.mark.asyncio
async def test_immediate_notification_writes_outbox_for_null_or_past_schedule():
    notifications_repo = FakeNotificationsRepo()
    outbox_repo = FakeOutboxRepo()
    service = NotificationsService(
        notifications_repository=notifications_repo,
        outbox_repository=outbox_repo,
        settings=Settings(),
        metrics=MetricsRegistry(),
    )

    immediate, created_immediate = await service.create_notification(
        conn=FakeConnection(),
        user_id=uuid4(),
        topic_id=uuid4(),
        payload={"title": "now"},
        scheduled_at=None,
        idempotency_key=None,
        request_id="req-now",
    )
    past, created_past = await service.create_notification(
        conn=FakeConnection(),
        user_id=uuid4(),
        topic_id=uuid4(),
        payload={"title": "past"},
        scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        idempotency_key=None,
        request_id="req-past",
    )

    assert created_immediate is True
    assert created_past is True
    assert immediate.status == "created"
    assert past.status == "created"
    assert len(outbox_repo.created_events) == 2


@pytest.mark.asyncio
async def test_cancel_allowed_only_for_scheduled_notifications():
    notifications_repo = FakeNotificationsRepo()
    service = NotificationsService(
        notifications_repository=notifications_repo,
        outbox_repository=FakeOutboxRepo(),
        settings=Settings(),
        metrics=MetricsRegistry(),
    )

    owner = uuid4()
    scheduled = await notifications_repo.create(
        conn=None,
        notification_id=uuid4(),
        topic_id=uuid4(),
        payload={"x": 1},
        scheduled_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        created_by=owner,
        idempotency_key="scheduled-cancel",
        status="scheduled",
    )
    created = await notifications_repo.create(
        conn=None,
        notification_id=uuid4(),
        topic_id=uuid4(),
        payload={"x": 2},
        scheduled_at=None,
        created_by=owner,
        idempotency_key="created-cancel",
        status="created",
    )

    cancelled = await service.cancel_notification(
        conn=None,
        notification_id=scheduled.id,
        user_id=owner,
        roles={"user"},
    )

    assert cancelled.status == "cancelled"

    with pytest.raises(ConflictError):
        await service.cancel_notification(
            conn=None,
            notification_id=created.id,
            user_id=owner,
            roles={"user"},
        )


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
        conn=None,
        notification_id=uuid4(),
        topic_id=uuid4(),
        payload={"x": 1},
        scheduled_at=None,
        created_by=owner,
        idempotency_key=None,
        status="created",
    )

    with pytest.raises(ForbiddenError):
        await service.get_notification(
            conn=None,
            notification_id=notification.id,
            user_id=uuid4(),
            roles={"user"},
        )
