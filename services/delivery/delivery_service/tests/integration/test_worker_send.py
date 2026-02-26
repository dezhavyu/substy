from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import pytest

from delivery_service.core.clock import Clock
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


class FixedClock:
    def __init__(self, now_value: datetime):
        self._now_value = now_value

    def now_utc(self) -> datetime:
        return self._now_value


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
            quiet_hours_start=None,
            quiet_hours_end=None,
            timezone="UTC",
        )

        fake_nats = FakeNATS()
        executor = DeliveryExecutorService(
            settings=settings,
            attempts_repository=repo,
            providers={"push": AlwaysSuccessProvider(), "email": AlwaysSuccessProvider(), "web": AlwaysSuccessProvider()},
            nats_client=fake_nats,
            metrics=MetricsRegistry(),
            clock=FixedClock(datetime(2026, 1, 1, 10, 0, tzinfo=UTC)),
        )

        await executor.execute_send(conn, redis_pool, attempt.id)

        status = await conn.fetchval("SELECT status FROM delivery.delivery_attempts WHERE id = $1", attempt.id)
        assert status == "sent"
        assert len(fake_nats.events) == 1
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_worker_delays_in_quiet_hours_then_sends_after_allowed_time(clean_database, redis_pool):
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
            quiet_hours_start=datetime.strptime("23:00:00", "%H:%M:%S").time(),
            quiet_hours_end=datetime.strptime("07:00:00", "%H:%M:%S").time(),
            timezone="Europe/Zurich",
        )

        fake_nats = FakeNATS()
        quiet_now = datetime(2026, 1, 1, 22, 30, tzinfo=UTC)  # 23:30 local in Zurich, inside quiet hours.
        executor_quiet = DeliveryExecutorService(
            settings=settings,
            attempts_repository=repo,
            providers={"push": AlwaysSuccessProvider(), "email": AlwaysSuccessProvider(), "web": AlwaysSuccessProvider()},
            nats_client=fake_nats,
            metrics=MetricsRegistry(),
            clock=FixedClock(quiet_now),
        )

        await executor_quiet.execute_send(conn, redis_pool, attempt.id)

        row = await conn.fetchrow(
            "SELECT status, next_retry_at, attempt_no FROM delivery.delivery_attempts WHERE id = $1",
            attempt.id,
        )
        assert row["status"] == "failed"
        assert row["attempt_no"] == 0
        assert row["next_retry_at"] == datetime(2026, 1, 2, 6, 0, tzinfo=UTC)

        executor_allowed = DeliveryExecutorService(
            settings=settings,
            attempts_repository=repo,
            providers={"push": AlwaysSuccessProvider(), "email": AlwaysSuccessProvider(), "web": AlwaysSuccessProvider()},
            nats_client=fake_nats,
            metrics=MetricsRegistry(),
            clock=FixedClock(datetime(2026, 1, 2, 6, 0, tzinfo=UTC)),
        )
        await executor_allowed.execute_send(conn, redis_pool, attempt.id)

        status = await conn.fetchval("SELECT status FROM delivery.delivery_attempts WHERE id = $1", attempt.id)
        assert status == "sent"
        assert len(fake_nats.events) == 1
    finally:
        await conn.close()
