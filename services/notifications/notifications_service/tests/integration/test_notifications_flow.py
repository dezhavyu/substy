from uuid import uuid4

import asyncpg
import pytest

from notifications_service.core.metrics import MetricsRegistry
from notifications_service.core.settings import get_settings
from notifications_service.infrastructure.db import Database
from notifications_service.repositories.outbox import OutboxRepository
from notifications_service.services.outbox_publisher import OutboxPublisher


class FakeNATSClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict, dict[str, str]]] = []

    async def publish_json(self, subject: str, payload: dict, headers: dict[str, str]) -> None:
        self.published.append((subject, payload, headers))


@pytest.mark.asyncio
async def test_create_notification_writes_outbox(client):
    user_id = str(uuid4())

    response = await client.post(
        "/notifications",
        headers={"X-User-Id": user_id, "X-Request-Id": "req-test"},
        json={
            "topic_id": str(uuid4()),
            "payload": {"message": "hello"},
            "scheduled_at": None,
            "idempotency_key": "key-1",
        },
    )

    assert response.status_code == 201

    settings = get_settings()
    conn = await asyncpg.connect(settings.database_dsn)
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM notifications.outbox_events")
        assert int(count) == 1
    finally:
        await conn.close()


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
            {"notification_id": str(uuid4())},
            {"request_id": "r-1", "user_id": str(uuid4())},
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
