from datetime import datetime, timezone
from uuid import uuid4

import pytest

from delivery_service.core.metrics import MetricsRegistry
from delivery_service.core.settings import Settings
from delivery_service.providers.base import DeliveryResult
from delivery_service.services.delivery_executor import DeliveryExecutorService


class FakeProvider:
    async def send(self, user_id, payload):
        return DeliveryResult(success=True)


class FakeAttempt:
    def __init__(self):
        self.id = uuid4()
        self.notification_id = uuid4()
        self.user_id = uuid4()
        self.channel = "push"
        self.payload = {"k": "v"}
        self.status = "sent"
        self.attempt_no = 0


class FakeRepository:
    async def get_for_update(self, conn, attempt_id):
        return FakeAttempt()

    async def mark_sent(self, conn, attempt_id):
        raise AssertionError("mark_sent should not be called for sent attempt")

    async def mark_failed(self, *args, **kwargs):
        raise AssertionError("mark_failed should not be called for sent attempt")


class FakeNATS:
    async def publish_json(self, subject, payload, headers=None):
        raise AssertionError("should not publish for already sent attempt")


class FakeRedis:
    async def enqueue_job(self, *args, **kwargs):
        raise AssertionError("should not enqueue retry for sent attempt")


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
    service = DeliveryExecutorService(
        settings=Settings(),
        attempts_repository=FakeRepository(),
        providers={"push": FakeProvider()},
        nats_client=FakeNATS(),
        metrics=MetricsRegistry(),
    )

    await service.execute_send(FakeConn(), FakeRedis(), uuid4())
