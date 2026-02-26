from datetime import UTC, datetime, time
from uuid import uuid4

import pytest

from delivery_service.core.metrics import MetricsRegistry
from delivery_service.core.settings import Settings
from delivery_service.providers.base import DeliveryResult
from delivery_service.services.delivery_executor import DeliveryExecutorService


class FixedClock:
    def __init__(self, current: datetime):
        self.current = current

    def now_utc(self) -> datetime:
        return self.current


class FakeProvider:
    def __init__(self, result: DeliveryResult | None = None):
        self._result = result or DeliveryResult(success=True)
        self.calls = 0

    async def send(self, user_id, payload):
        self.calls += 1
        return self._result


class FakeAttempt:
    def __init__(
        self,
        status: str = "pending",
        attempt_no: int = 0,
        quiet_hours_start: time | None = None,
        quiet_hours_end: time | None = None,
        timezone: str = "UTC",
    ):
        self.id = uuid4()
        self.notification_id = uuid4()
        self.user_id = uuid4()
        self.channel = "push"
        self.payload = {"k": "v"}
        self.status = status
        self.attempt_no = attempt_no
        self.next_retry_at = None
        self.quiet_hours_start = quiet_hours_start
        self.quiet_hours_end = quiet_hours_end
        self.timezone = timezone


class FakeRepository:
    def __init__(self, attempt: FakeAttempt):
        self._attempt = attempt
        self.mark_sent_calls = 0
        self.mark_failed_calls: list[dict] = []
        self.mark_delayed_calls: list[dict] = []

    async def get_for_update(self, conn, attempt_id):
        return self._attempt

    async def mark_sent(self, conn, attempt_id):
        self.mark_sent_calls += 1

    async def mark_failed(self, conn, attempt_id, attempt_no, error_code, error_message, next_retry_at, dead):
        self.mark_failed_calls.append(
            {
                "attempt_no": attempt_no,
                "error_code": error_code,
                "next_retry_at": next_retry_at,
                "dead": dead,
            }
        )

    async def mark_delayed(self, conn, attempt_id, next_retry_at, error_code, error_message):
        self.mark_delayed_calls.append(
            {
                "next_retry_at": next_retry_at,
                "error_code": error_code,
            }
        )


class FakeNATS:
    def __init__(self):
        self.published = []

    async def publish_json(self, subject, payload, headers=None):
        self.published.append((subject, payload, headers))


class FakeRedis:
    def __init__(self):
        self.jobs = []

    async def enqueue_job(self, name, *args, **kwargs):
        self.jobs.append((name, args, kwargs))


class FakeConn:
    class Tx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def transaction(self):
        return FakeConn.Tx()


@pytest.mark.asyncio
async def test_sent_attempt_is_idempotent_noop():
    attempt = FakeAttempt(status="sent")
    repo = FakeRepository(attempt)
    provider = FakeProvider()
    nats = FakeNATS()
    redis = FakeRedis()

    service = DeliveryExecutorService(
        settings=Settings(),
        attempts_repository=repo,
        providers={"push": provider},
        nats_client=nats,
        metrics=MetricsRegistry(),
        clock=FixedClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC)),
    )

    await service.execute_send(FakeConn(), redis, uuid4())

    assert repo.mark_sent_calls == 0
    assert repo.mark_failed_calls == []
    assert repo.mark_delayed_calls == []
    assert provider.calls == 0
    assert redis.jobs == []


@pytest.mark.asyncio
async def test_quiet_hours_delay_defers_send_without_provider_call():
    attempt = FakeAttempt(
        status="pending",
        quiet_hours_start=time(22, 0),
        quiet_hours_end=time(7, 0),
        timezone="UTC",
    )
    repo = FakeRepository(attempt)
    provider = FakeProvider()
    nats = FakeNATS()
    redis = FakeRedis()
    metrics = MetricsRegistry()

    now = datetime(2026, 1, 1, 23, 30, tzinfo=UTC)
    service = DeliveryExecutorService(
        settings=Settings(),
        attempts_repository=repo,
        providers={"push": provider},
        nats_client=nats,
        metrics=metrics,
        clock=FixedClock(now),
    )

    await service.execute_send(FakeConn(), redis, attempt.id)

    assert provider.calls == 0
    assert len(repo.mark_delayed_calls) == 1
    assert repo.mark_delayed_calls[0]["error_code"] == "quiet_hours"
    assert repo.mark_delayed_calls[0]["next_retry_at"] == datetime(2026, 1, 2, 7, 0, tzinfo=UTC)
    assert metrics.delivery_delayed_quiet_hours_total["push"] == 1
    assert len(redis.jobs) == 1
    assert redis.jobs[0][0] == "retry_attempt"


@pytest.mark.asyncio
async def test_provider_failure_retry_respects_quiet_hours_end():
    settings = Settings(
        DELIVERY_BASE_DELAY_SECONDS=5,
        DELIVERY_MAX_DELAY_SECONDS=3600,
        DELIVERY_RETRY_JITTER_SECONDS=0,
    )
    attempt = FakeAttempt(
        status="pending",
        attempt_no=0,
        quiet_hours_start=time(22, 0),
        quiet_hours_end=time(7, 0),
        timezone="UTC",
    )
    repo = FakeRepository(attempt)
    provider = FakeProvider(DeliveryResult(success=False, error_code="x", error_message="y"))
    nats = FakeNATS()
    redis = FakeRedis()

    # Backoff schedules inside quiet hours (22:00-07:00), so retry must move to quiet end.
    now = datetime(2026, 1, 1, 21, 59, 58, tzinfo=UTC)
    service = DeliveryExecutorService(
        settings=settings,
        attempts_repository=repo,
        providers={"push": provider},
        nats_client=nats,
        metrics=MetricsRegistry(),
        clock=FixedClock(now),
    )

    await service.execute_send(FakeConn(), redis, attempt.id)

    assert provider.calls == 1
    assert len(repo.mark_failed_calls) == 1
    assert repo.mark_failed_calls[0]["dead"] is False
    assert repo.mark_failed_calls[0]["next_retry_at"] == datetime(2026, 1, 2, 7, 0, tzinfo=UTC)
