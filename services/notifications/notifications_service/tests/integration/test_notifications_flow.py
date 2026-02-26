import json
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import pytest

from notifications_service.core.metrics import MetricsRegistry
from notifications_service.core.settings import get_settings
from notifications_service.infrastructure.db import Database
from notifications_service.repositories.notifications import NotificationsRepository
from notifications_service.repositories.outbox import OutboxRepository
from notifications_service.services.outbox_publisher import OutboxPublisher
from notifications_service.services.scheduler_service import SchedulerService


class FakeNATSClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict, dict[str, str]]] = []

    async def publish_json(self, subject: str, payload: dict, headers: dict[str, str]) -> None:
        self.published.append((subject, payload, headers))


def _scheduler_service() -> SchedulerService:
    return SchedulerService(
        notifications_repository=NotificationsRepository(),
        outbox_repository=OutboxRepository(),
        settings=get_settings(),
        metrics=MetricsRegistry(),
    )


@pytest.mark.asyncio
async def test_create_notification_writes_outbox_for_immediate(client):
    user_id = str(uuid4())

    response = await client.post(
        "/notifications",
        headers={"X-User-Id": user_id, "X-Request-Id": "req-test"},
        json={
            "topic_id": str(uuid4()),
            "payload": {"message": "hello"},
            "scheduled_at": None,
            "idempotency_key": "key-immediate",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "created"

    settings = get_settings()
    conn = await asyncpg.connect(settings.database_dsn)
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM notifications.outbox_events")
        assert int(count) == 1
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_create_notification_future_is_scheduled_without_outbox(client):
    user_id = str(uuid4())
    scheduled_at = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()

    response = await client.post(
        "/notifications",
        headers={"X-User-Id": user_id, "X-Request-Id": "req-future"},
        json={
            "topic_id": str(uuid4()),
            "payload": {"message": "scheduled"},
            "scheduled_at": scheduled_at,
            "idempotency_key": "key-future",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "scheduled"

    settings = get_settings()
    conn = await asyncpg.connect(settings.database_dsn)
    try:
        outbox_count = await conn.fetchval("SELECT COUNT(*) FROM notifications.outbox_events")
        assert int(outbox_count) == 0
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_scheduler_tick_queues_due_and_writes_outbox(client):
    user_id = str(uuid4())
    topic_id = str(uuid4())
    scheduled_at = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()

    create_resp = await client.post(
        "/notifications",
        headers={"X-User-Id": user_id, "X-Request-Id": "req-scheduled"},
        json={
            "topic_id": topic_id,
            "payload": {"message": "tick"},
            "scheduled_at": scheduled_at,
            "idempotency_key": "tick-key",
        },
    )
    assert create_resp.status_code == 201
    created_body = create_resp.json()
    notification_id = created_body["id"]
    assert created_body["status"] == "scheduled"

    scheduled_at_value = datetime.fromisoformat(created_body["scheduled_at"].replace("Z", "+00:00"))
    wait_seconds = max(0.0, (scheduled_at_value - datetime.now(timezone.utc)).total_seconds()) + 0.25
    await asyncio.sleep(wait_seconds)

    settings = get_settings()
    conn = await asyncpg.connect(settings.database_dsn)
    try:
        result = await _scheduler_service().run_one_tick(conn, request_id="it-scheduler")
        assert result.picked_count == 1

        status = await conn.fetchval(
            "SELECT status FROM notifications.notifications WHERE id = $1::uuid",
            notification_id,
        )
        assert status == "queued"

        outbox_count = await conn.fetchval(
            "SELECT COUNT(*) FROM notifications.outbox_events WHERE aggregate_id = $1::uuid",
            notification_id,
        )
        assert int(outbox_count) == 1
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_scheduler_concurrency_skip_locked_creates_single_outbox(clean_database):
    settings = get_settings()
    notification_id = uuid4()

    conn = await asyncpg.connect(settings.database_dsn)
    try:
        await conn.execute(
            """
            INSERT INTO notifications.notifications (
                id, topic_id, payload, scheduled_at, status, created_by, idempotency_key
            ) VALUES ($1, $2, $3::jsonb, now() - interval '1 second', 'scheduled', $4, NULL)
            """,
            notification_id,
            uuid4(),
            json.dumps({"message": "concurrent"}, separators=(",", ":")),
            uuid4(),
        )
    finally:
        await conn.close()

    conn1 = await asyncpg.connect(settings.database_dsn)
    conn2 = await asyncpg.connect(settings.database_dsn)
    try:
        service = _scheduler_service()
        results = await asyncio.gather(
            service.run_one_tick(conn1, request_id="tick-1"),
            service.run_one_tick(conn2, request_id="tick-2"),
        )

        assert sorted(result.picked_count for result in results) == [0, 1]

        verify_conn = await asyncpg.connect(settings.database_dsn)
        try:
            status = await verify_conn.fetchval(
                "SELECT status FROM notifications.notifications WHERE id = $1",
                notification_id,
            )
            assert status == "queued"

            outbox_count = await verify_conn.fetchval(
                "SELECT COUNT(*) FROM notifications.outbox_events WHERE aggregate_id = $1",
                notification_id,
            )
            assert int(outbox_count) == 1
        finally:
            await verify_conn.close()
    finally:
        await conn1.close()
        await conn2.close()


@pytest.mark.asyncio
async def test_outbox_publisher_publishes_events(clean_database):
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_dsn)
    try:
        await conn.execute(
            """
            INSERT INTO notifications.outbox_events (
                id, aggregate_type, aggregate_id, event_type, payload, headers
            ) VALUES ($1, 'notification', $2, 'notification.created.v1', $3::jsonb, $4::jsonb)
            """,
            uuid4(),
            uuid4(),
            json.dumps({"notification_id": str(uuid4())}, separators=(",", ":")),
            json.dumps({"request_id": "r-1", "user_id": str(uuid4())}, separators=(",", ":")),
        )
    finally:
        await conn.close()

    db = Database(settings)
    await db.startup()
    fake_nats = FakeNATSClient()
    publisher = OutboxPublisher(
        db=db,
        nats_client=fake_nats,
        outbox_repository=OutboxRepository(),
        metrics=MetricsRegistry(),
        settings=settings,
    )

    try:
        await publisher.publish_batch()
    finally:
        await db.shutdown()

    assert len(fake_nats.published) == 1


@pytest.mark.asyncio
async def test_list_my_pagination(client):
    user_id = str(uuid4())

    for index in range(3):
        resp = await client.post(
            "/notifications",
            headers={"X-User-Id": user_id},
            json={
                "topic_id": str(uuid4()),
                "payload": {"n": index},
                "idempotency_key": f"idem-{index}",
            },
        )
        assert resp.status_code in (200, 201)

    first_page = await client.get("/notifications/me", headers={"X-User-Id": user_id}, params={"limit": 2})
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body["items"]) == 2
    assert first_body["next_cursor"] is not None

    second_page = await client.get(
        "/notifications/me",
        headers={"X-User-Id": user_id},
        params={"limit": 2, "cursor": first_body["next_cursor"]},
    )
    assert second_page.status_code == 200
    second_body = second_page.json()
    assert len(second_body["items"]) == 1
