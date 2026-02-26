from uuid import uuid4

import asyncpg
import pytest

from delivery_service.core.metrics import MetricsRegistry
from delivery_service.core.settings import get_settings
from delivery_service.providers.base import DeliveryResult
from delivery_service.repositories.delivery_attempts import DeliveryAttemptsRepository
from delivery_service.services.delivery_executor import DeliveryExecutorService


class AlwaysSuccessProvider:
    async def send(self, user_id, payload):
        return DeliveryResult(success=True)


class FakeNATS:
    def __init__(self):
        self.events = []

    async def publish_json(self, subject, payload, headers=None):
        self.events.append((subject, payload))


@pytest.mark.asyncio
async def test_worker_marks_attempt_sent(clean_database, redis_pool):
    settings = get_settings()
    repo = DeliveryAttemptsRepository()

    conn = await asyncpg.connect(settings.database_dsn)
    try:
        attempt, _ = await repo.create_or_get(
            conn=conn,
            attempt_id=uuid4(),
            notification_id=uuid4(),
            user_id=uuid4(),
            channel="push",
            payload={"x": 1},
        )

        fake_nats = FakeNATS()
        executor = DeliveryExecutorService(
            settings=settings,
            attempts_repository=repo,
            providers={"push": AlwaysSuccessProvider(), "email": AlwaysSuccessProvider(), "web": AlwaysSuccessProvider()},
            nats_client=fake_nats,
            metrics=MetricsRegistry(),
        )

        await executor.execute_send(conn, redis_pool, attempt.id)

        status = await conn.fetchval("SELECT status FROM delivery.delivery_attempts WHERE id = $1", attempt.id)
        assert status == "sent"
        assert len(fake_nats.events) == 1
    finally:
        await conn.close()
