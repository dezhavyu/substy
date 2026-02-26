from uuid import UUID, uuid4

import asyncpg
from arq.connections import ArqRedis

from delivery_service.core.metrics import MetricsRegistry
from delivery_service.core.settings import Settings
from delivery_service.repositories.delivery_attempts import DeliveryAttemptsRepository
from delivery_service.repositories.processed_events import ProcessedEventsRepository
from delivery_service.schemas.events import NotificationCreatedEvent
from delivery_service.services.subscriptions_fetcher import SubscriptionsFetcherService


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

            created_attempts = 0
            async for user_id in self._fetcher.iter_subscribers(event.topic_id):
                for channel in self._settings.channels:
                    attempt, created = await self._attempts.create_or_get(
                        conn=conn,
                        attempt_id=uuid4(),
                        notification_id=event.notification_id,
                        user_id=user_id,
                        channel=channel,
                        payload=event.payload,
                    )
                    await redis.enqueue_job(f"send_{channel}", str(attempt.id))
                    if created:
                        created_attempts += 1

            self._metrics.inc_attempts_created(created_attempts)
            self._metrics.inc_jetstream_processed()
            return True
