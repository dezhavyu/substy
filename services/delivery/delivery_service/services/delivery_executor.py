import logging
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
from arq.connections import ArqRedis

from delivery_service.core.backoff import compute_backoff_delay
from delivery_service.core.clock import Clock, SystemClock
from delivery_service.core.metrics import MetricsRegistry
from delivery_service.core.quiet_hours import compute_next_allowed_time, resolve_timezone
from delivery_service.core.settings import Settings
from delivery_service.infrastructure.nats_client import NATSClient
from delivery_service.providers.base import DeliveryProvider
from delivery_service.repositories.delivery_attempts import DeliveryAttemptsRepository
from delivery_service.repositories.records import DeliveryAttemptRecord

logger = logging.getLogger(__name__)


class DeliveryExecutorService:
    def __init__(
        self,
        settings: Settings,
        attempts_repository: DeliveryAttemptsRepository,
        providers: dict[str, DeliveryProvider],
        nats_client: NATSClient,
        metrics: MetricsRegistry,
        clock: Clock | None = None,
    ) -> None:
        self._settings = settings
        self._attempts = attempts_repository
        self._providers = providers
        self._nats = nats_client
        self._metrics = metrics
        self._clock = clock or SystemClock()

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

            now_utc = self._clock.now_utc()

            if attempt.status in {"sent", "dead"}:
                return

            if attempt.next_retry_at is not None and attempt.next_retry_at > now_utc:
                return

            quiet_retry_at = self._next_quiet_hours_retry(now_utc, attempt)
            if quiet_retry_at is not None:
                delay_seconds = max((quiet_retry_at - now_utc).total_seconds(), 0.0)
                await self._attempts.mark_delayed(
                    conn=conn,
                    attempt_id=attempt.id,
                    next_retry_at=quiet_retry_at,
                    error_code="quiet_hours",
                    error_message="Delivery delayed due to quiet hours",
                )
                self._metrics.inc_delayed_quiet_hours(attempt.channel)
                self._metrics.observe_delivery_delay(delay_seconds)
                await redis.enqueue_job(
                    "retry_attempt",
                    str(attempt.id),
                    attempt.channel,
                    _defer_by=timedelta(seconds=delay_seconds),
                )
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
                        "delivered_at": now_utc.isoformat(),
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
                        "failed_at": now_utc.isoformat(),
                    },
                )
                return

            delay_seconds = compute_backoff_delay(
                attempt_no=next_attempt_no,
                base_delay_seconds=self._settings.delivery_base_delay_seconds,
                max_delay_seconds=self._settings.delivery_max_delay_seconds,
                jitter_max_seconds=self._settings.delivery_retry_jitter_seconds,
            )
            backoff_retry_at = now_utc + timedelta(seconds=delay_seconds)

            quiet_retry_at = self._next_quiet_hours_retry(backoff_retry_at, attempt)
            next_retry_at = backoff_retry_at
            if quiet_retry_at is not None and quiet_retry_at > next_retry_at:
                next_retry_at = quiet_retry_at

            retry_delay_seconds = max((next_retry_at - now_utc).total_seconds(), 0.0)

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
            self._metrics.observe_delivery_delay(retry_delay_seconds)

            await redis.enqueue_job(
                "retry_attempt",
                str(attempt.id),
                attempt.channel,
                _defer_by=timedelta(seconds=retry_delay_seconds),
            )

    def _next_quiet_hours_retry(
        self,
        now_utc: datetime,
        attempt: DeliveryAttemptRecord,
    ) -> datetime | None:
        if attempt.quiet_hours_start is None or attempt.quiet_hours_end is None:
            return None

        timezone_name = attempt.timezone or "UTC"
        _, valid_timezone = resolve_timezone(timezone_name)
        if not valid_timezone:
            logger.warning(
                "Invalid subscriber timezone; fallback to UTC",
                extra={
                    "user_id": str(attempt.user_id),
                    "timezone": timezone_name,
                },
            )
            timezone_name = "UTC"

        next_allowed_at = compute_next_allowed_time(
            now_utc=now_utc,
            timezone_name=timezone_name,
            quiet_hours_start=attempt.quiet_hours_start,
            quiet_hours_end=attempt.quiet_hours_end,
        )

        if next_allowed_at <= now_utc:
            return None
        return next_allowed_at
