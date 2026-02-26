from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
from arq.connections import ArqRedis

from delivery_service.core.backoff import compute_backoff_delay
from delivery_service.core.metrics import MetricsRegistry
from delivery_service.core.settings import Settings
from delivery_service.infrastructure.nats_client import NATSClient
from delivery_service.providers.base import DeliveryProvider
from delivery_service.repositories.delivery_attempts import DeliveryAttemptsRepository


class DeliveryExecutorService:
    def __init__(
        self,
        settings: Settings,
        attempts_repository: DeliveryAttemptsRepository,
        providers: dict[str, DeliveryProvider],
        nats_client: NATSClient,
        metrics: MetricsRegistry,
    ) -> None:
        self._settings = settings
        self._attempts = attempts_repository
        self._providers = providers
        self._nats = nats_client
        self._metrics = metrics

    async def execute_send(
        self,
        conn: asyncpg.Connection,
        redis: ArqRedis,
        attempt_id: UUID,
    ) -> None:
        async with conn.transaction():
            attempt = await self._attempts.get_for_update(conn, attempt_id)
            if attempt is None:
                return

            if attempt.status in {"sent", "dead"}:
                return

            provider = self._providers.get(attempt.channel)
            if provider is None:
                raise RuntimeError(f"No provider configured for channel={attempt.channel}")

            result = await provider.send(attempt.user_id, attempt.payload)
            if result.success:
                await self._attempts.mark_sent(conn, attempt.id)
                self._metrics.inc_sent()
                await self._nats.publish_json(
                    self._settings.nats_subject_delivery_succeeded,
                    {
                        "event_id": str(uuid4()),
                        "notification_id": str(attempt.notification_id),
                        "user_id": str(attempt.user_id),
                        "channel": attempt.channel,
                        "attempt_id": str(attempt.id),
                        "delivered_at": datetime.now(UTC).isoformat(),
                    },
                )
                return

            next_attempt_no = attempt.attempt_no + 1
            dead = next_attempt_no >= self._settings.delivery_max_attempts

            if dead:
                await self._attempts.mark_failed(
                    conn=conn,
                    attempt_id=attempt.id,
                    attempt_no=next_attempt_no,
                    error_code=result.error_code or "delivery_failed",
                    error_message=result.error_message or "Delivery failed",
                    next_retry_at=None,
                    dead=True,
                )
                self._metrics.inc_dead()
                await self._nats.publish_json(
                    self._settings.nats_subject_delivery_failed,
                    {
                        "event_id": str(uuid4()),
                        "notification_id": str(attempt.notification_id),
                        "user_id": str(attempt.user_id),
                        "channel": attempt.channel,
                        "attempt_id": str(attempt.id),
                        "error_code": result.error_code or "delivery_failed",
                        "error_message": (result.error_message or "Delivery failed")[:120],
                        "failed_at": datetime.now(UTC).isoformat(),
                    },
                )
                return

            delay_seconds = compute_backoff_delay(
                attempt_no=next_attempt_no,
                base_delay_seconds=self._settings.delivery_base_delay_seconds,
                max_delay_seconds=self._settings.delivery_max_delay_seconds,
                jitter_max_seconds=self._settings.delivery_retry_jitter_seconds,
            )
            next_retry_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)

            await self._attempts.mark_failed(
                conn=conn,
                attempt_id=attempt.id,
                attempt_no=next_attempt_no,
                error_code=result.error_code or "delivery_failed",
                error_message=result.error_message or "Delivery failed",
                next_retry_at=next_retry_at,
                dead=False,
            )
            self._metrics.inc_failed()

            await redis.enqueue_job(
                "retry_attempt",
                str(attempt.id),
                attempt.channel,
                _defer_by=timedelta(seconds=delay_seconds),
            )
