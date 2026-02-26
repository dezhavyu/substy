import logging
from collections import defaultdict
from uuid import UUID, uuid4

import asyncpg
from arq.connections import ArqRedis

from delivery_service.core.metrics import MetricsRegistry
from delivery_service.core.settings import Settings
from delivery_service.repositories.delivery_attempts import DeliveryAttemptsRepository
from delivery_service.repositories.processed_events import ProcessedEventsRepository
from delivery_service.schemas.events import NotificationCreatedEvent
from delivery_service.services.subscriptions_fetcher import SubscriptionsFetcherService

logger = logging.getLogger(__name__)


class FanoutService:
    def __init__(
        self,
        settings: Settings,
        processed_events_repository: ProcessedEventsRepository,
        attempts_repository: DeliveryAttemptsRepository,
        subscriptions_fetcher: SubscriptionsFetcherService,
        metrics: MetricsRegistry,
    ) -> None:
        self._settings = settings
        self._processed = processed_events_repository
        self._attempts = attempts_repository
        self._fetcher = subscriptions_fetcher
        self._metrics = metrics

    async def process_notification_created(
        self,
        conn: asyncpg.Connection,
        redis: ArqRedis,
        event: NotificationCreatedEvent,
        subject: str,
    ) -> bool:
        async with conn.transaction():
            is_new = await self._processed.try_mark_processed(conn, event.event_id, subject)
            if not is_new:
                return False

            created_attempts_by_channel: dict[str, int] = defaultdict(int)
            async for subscriber in self._fetcher.iter_subscribers(event.topic_id):
                try:
                    subscriber_user_id = UUID(subscriber.user_id)
                except ValueError:
                    logger.warning(
                        "Skipping subscriber with invalid user_id",
                        extra={
                            "topic_id": str(event.topic_id),
                            "user_id": subscriber.user_id,
                            "subscription_id": subscriber.subscription_id,
                        },
                    )
                    continue
                channels = self._normalize_channels(subscriber.channels)
                if not channels:
                    logger.warning(
                        "Skipping subscriber with empty channels",
                        extra={
                            "topic_id": str(event.topic_id),
                            "user_id": subscriber.user_id,
                            "subscription_id": subscriber.subscription_id,
                        },
                    )
                    continue

                timezone = subscriber.timezone.strip() if subscriber.timezone else "UTC"

                for channel in channels:
                    if channel not in self._settings.channels:
                        logger.warning(
                            "Skipping unsupported delivery channel",
                            extra={
                                "channel": channel,
                                "topic_id": str(event.topic_id),
                                "user_id": subscriber.user_id,
                            },
                        )
                        continue
                    attempt, created = await self._attempts.create_or_get(
                        conn=conn,
                        attempt_id=uuid4(),
                        notification_id=event.notification_id,
                        user_id=subscriber_user_id,
                        channel=channel,
                        payload=event.payload,
                        quiet_hours_start=subscriber.quiet_hours_start,
                        quiet_hours_end=subscriber.quiet_hours_end,
                        timezone=timezone,
                    )
                    await redis.enqueue_job(f"send_{channel}", str(attempt.id))
                    if created:
                        created_attempts_by_channel[channel] += 1

            for channel, value in created_attempts_by_channel.items():
                self._metrics.inc_attempts_created(channel, value)
            self._metrics.inc_jetstream_processed()
            return True

    @staticmethod
    def _normalize_channels(channels: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for channel in channels:
            lowered = channel.strip().lower()
            if lowered and lowered not in seen:
                seen.add(lowered)
                normalized.append(lowered)
        return normalized
