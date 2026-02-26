from uuid import uuid4

import asyncpg
import pytest

from delivery_service.core.metrics import MetricsRegistry
from delivery_service.core.settings import get_settings
from delivery_service.repositories.delivery_attempts import DeliveryAttemptsRepository
from delivery_service.repositories.processed_events import ProcessedEventsRepository
from delivery_service.schemas.events import NotificationCreatedEvent
from delivery_service.services.fanout import FanoutService
from delivery_service.services.subscriptions_fetcher import SubscriptionsFetcherService


class FakeSubscriptionsClient:
    def __init__(self, pages):
        self.pages = pages
        self.idx = 0

    async def fetch_subscribers_page(self, topic_id: str, cursor: str | None):
        page = self.pages[self.idx]
        self.idx += 1
        return page


@pytest.mark.asyncio
async def test_fanout_creates_attempts_and_is_idempotent(clean_database, redis_pool):
    settings = get_settings()

    event_id = uuid4()
    event = NotificationCreatedEvent(
        event_id=event_id,
        notification_id=uuid4(),
        topic_id=uuid4(),
        created_by=uuid4(),
        payload={"title": "hello"},
        scheduled_at=None,
        created_at="2026-01-01T00:00:00Z",
    )

    user1 = str(uuid4())
    user2 = str(uuid4())
    user3 = str(uuid4())

    pages = [
        {
            "items": [
                {
                    "user_id": user1,
                    "subscription_id": str(uuid4()),
                    "channels": ["push", "email"],
                    "quiet_hours_start": "22:00:00",
                    "quiet_hours_end": "07:00:00",
                    "timezone": "UTC",
                },
                {
                    "user_id": user2,
                    "subscription_id": str(uuid4()),
                    "channels": ["web"],
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": "Europe/Zurich",
                },
            ],
            "next_cursor": "abc",
        },
        {
            "items": [
                {
                    "user_id": user3,
                    "subscription_id": str(uuid4()),
                    "channels": ["push"],
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "timezone": "UTC",
                }
            ],
            "next_cursor": None,
        },
    ]

    service = FanoutService(
        settings=settings,
        processed_events_repository=ProcessedEventsRepository(),
        attempts_repository=DeliveryAttemptsRepository(),
        subscriptions_fetcher=SubscriptionsFetcherService(FakeSubscriptionsClient(pages)),
        metrics=MetricsRegistry(),
    )

    conn = await asyncpg.connect(settings.database_dsn)
    try:
        created = await service.process_notification_created(conn, redis_pool, event, "notification.created.v1")
        assert created is True

        duplicate = await service.process_notification_created(conn, redis_pool, event, "notification.created.v1")
        assert duplicate is False

        attempts = await conn.fetchval("SELECT COUNT(*) FROM delivery.delivery_attempts")
        assert int(attempts) == 4
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_subscribers_pagination_is_fully_processed(clean_database, redis_pool):
    settings = get_settings()

    users_page_1 = [str(uuid4()), str(uuid4())]
    users_page_2 = [str(uuid4())]

    service = FanoutService(
        settings=settings,
        processed_events_repository=ProcessedEventsRepository(),
        attempts_repository=DeliveryAttemptsRepository(),
        subscriptions_fetcher=SubscriptionsFetcherService(
            FakeSubscriptionsClient(
                [
                    {
                        "items": [
                            {
                                "user_id": u,
                                "subscription_id": str(uuid4()),
                                "channels": ["push"],
                                "quiet_hours_start": None,
                                "quiet_hours_end": None,
                                "timezone": "UTC",
                            }
                            for u in users_page_1
                        ],
                        "next_cursor": "next",
                    },
                    {
                        "items": [
                            {
                                "user_id": u,
                                "subscription_id": str(uuid4()),
                                "channels": ["email", "web"],
                                "quiet_hours_start": "23:00:00",
                                "quiet_hours_end": "06:00:00",
                                "timezone": "Europe/Zurich",
                            }
                            for u in users_page_2
                        ],
                        "next_cursor": None,
                    },
                ]
            )
        ),
        metrics=MetricsRegistry(),
    )

    event = NotificationCreatedEvent(
        event_id=uuid4(),
        notification_id=uuid4(),
        topic_id=uuid4(),
        created_by=uuid4(),
        payload={"p": 1},
        scheduled_at=None,
        created_at="2026-01-01T00:00:00Z",
    )

    conn = await asyncpg.connect(settings.database_dsn)
    try:
        await service.process_notification_created(conn, redis_pool, event, "notification.created.v1")
        users = await conn.fetch("SELECT DISTINCT user_id FROM delivery.delivery_attempts")
        fetched_users = {str(row["user_id"]) for row in users}
        assert fetched_users == set(users_page_1 + users_page_2)

        attempts_count = await conn.fetchval("SELECT COUNT(*) FROM delivery.delivery_attempts")
        assert int(attempts_count) == 2 + 2
    finally:
        await conn.close()
