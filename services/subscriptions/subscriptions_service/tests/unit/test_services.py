from datetime import datetime, time, timezone as dt_timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from subscriptions_service.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from subscriptions_service.repositories.records import (
    SubscriberRecord,
    SubscriptionPreferencesRecord,
    SubscriptionRecord,
    TopicRecord,
)
from subscriptions_service.schemas.subscriptions import (
    QuietHoursPatchRequest,
    SubscriptionPreferencesPatchRequest,
)
from subscriptions_service.services.subscriptions import SubscriptionsService
from subscriptions_service.services.topics import TopicsService


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def transaction(self):
        return FakeTransaction()


class FakeTopicsRepository:
    def __init__(self) -> None:
        self.topics: dict[UUID, TopicRecord] = {}

    async def create(self, conn, topic_id, key, name, description):
        topic = TopicRecord(
            id=topic_id,
            key=key,
            name=name,
            description=description,
            created_at=datetime.now(dt_timezone.utc),
        )
        self.topics[topic_id] = topic
        return topic

    async def get_by_id(self, conn, topic_id):
        return self.topics.get(topic_id)

    async def list_topics(self, conn, q, limit, cursor_created_at, cursor_id):
        rows = sorted(self.topics.values(), key=lambda x: (x.created_at, x.id), reverse=True)
        return rows[:limit]


class FakeSubscriptionsRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, SubscriptionRecord] = {}

    async def create(self, conn, subscription_id, user_id, topic_id):
        now = datetime.now(dt_timezone.utc)
        row = SubscriptionRecord(
            id=subscription_id,
            user_id=user_id,
            topic_id=topic_id,
            is_active=True,
            preferences=SubscriptionPreferencesRecord(
                channels=["push"],
                quiet_hours_start=None,
                quiet_hours_end=None,
                timezone="UTC",
                updated_at=now,
            ),
            created_at=now,
            updated_at=now,
        )
        self.rows[subscription_id] = row
        return row

    async def get_by_user_topic(self, conn, user_id, topic_id):
        for row in self.rows.values():
            if row.user_id == user_id and row.topic_id == topic_id:
                return row
        return None

    async def get_by_id_for_user(self, conn, subscription_id, user_id):
        row = self.rows.get(subscription_id)
        if row and row.user_id == user_id:
            return row
        return None

    async def list_for_user(self, conn, user_id, limit, cursor_created_at, cursor_id):
        rows = [x for x in self.rows.values() if x.user_id == user_id]
        rows.sort(key=lambda x: (x.created_at, x.id), reverse=True)
        return rows[:limit]

    async def update_active(self, conn, subscription_id, user_id, is_active):
        row = self.rows.get(subscription_id)
        if row is None or row.user_id != user_id:
            return None

        row.is_active = is_active
        row.updated_at = datetime.now(dt_timezone.utc)
        return row

    async def upsert_preferences(
        self,
        conn,
        subscription_id,
        channels,
        quiet_hours_start,
        quiet_hours_end,
        timezone,
    ):
        row = self.rows.get(subscription_id)
        if row is None:
            return

        row.preferences = SubscriptionPreferencesRecord(
            channels=channels,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
            timezone=timezone,
            updated_at=datetime.now(dt_timezone.utc),
        )

    async def list_active_subscribers(self, conn, topic_id, limit, cursor_user_id, cursor_subscription_id):
        rows = [x for x in self.rows.values() if x.topic_id == topic_id and x.is_active]
        rows.sort(key=lambda x: (x.user_id, x.id))
        return [
            SubscriberRecord(
                user_id=x.user_id,
                subscription_id=x.id,
                channels=x.preferences.channels,
                quiet_hours_start=x.preferences.quiet_hours_start,
                quiet_hours_end=x.preferences.quiet_hours_end,
                timezone=x.preferences.timezone,
            )
            for x in rows[:limit]
        ]


@pytest.mark.asyncio
async def test_subscribe_is_idempotent():
    conn = FakeConnection()
    topics = FakeTopicsRepository()
    subscriptions = FakeSubscriptionsRepository()

    topic = await topics.create(conn, uuid4(), "news", "News", None)
    service = SubscriptionsService(subscriptions, topics)

    user_id = uuid4()
    first, created1 = await service.subscribe(conn, user_id, topic.id)
    second, created2 = await service.subscribe(conn, user_id, topic.id)

    assert created1 is True
    assert created2 is False
    assert first.id == second.id
    assert first.preferences.channels == ["push"]


@pytest.mark.asyncio
async def test_create_topic_requires_admin_role():
    service = TopicsService(FakeTopicsRepository())

    with pytest.raises(ForbiddenError):
        await service.create_topic(None, roles={"user"}, key="news", name="News", description=None)


@pytest.mark.asyncio
async def test_unsubscribe_missing_subscription_raises_not_found():
    conn = FakeConnection()
    topics = FakeTopicsRepository()
    subscriptions = FakeSubscriptionsRepository()
    service = SubscriptionsService(subscriptions, topics)

    with pytest.raises(NotFoundError):
        await service.unsubscribe(conn, user_id=uuid4(), subscription_id=uuid4())


@pytest.mark.asyncio
async def test_update_preferences_supports_cross_midnight_quiet_hours():
    conn = FakeConnection()
    topics = FakeTopicsRepository()
    subscriptions = FakeSubscriptionsRepository()
    service = SubscriptionsService(subscriptions, topics)

    topic = await topics.create(conn, uuid4(), "alerts", "Alerts", None)
    user_id = uuid4()
    created, _ = await service.subscribe(conn, user_id, topic.id)

    updated = await service.update_subscription(
        conn=conn,
        user_id=user_id,
        subscription_id=created.id,
        is_active=None,
        preferences_patch=SubscriptionPreferencesPatchRequest(
            channels=["push", "email"],
            quiet_hours=QuietHoursPatchRequest(start=time(22, 0, 0), end=time(7, 0, 0)),
            timezone="Europe/Zurich",
        ),
    )

    assert updated.preferences.channels == ["push", "email"]
    assert updated.preferences.quiet_hours_start == time(22, 0, 0)
    assert updated.preferences.quiet_hours_end == time(7, 0, 0)
    assert updated.preferences.timezone == "Europe/Zurich"


@pytest.mark.asyncio
async def test_update_preferences_start_equals_end_disables_quiet_hours():
    conn = FakeConnection()
    topics = FakeTopicsRepository()
    subscriptions = FakeSubscriptionsRepository()
    service = SubscriptionsService(subscriptions, topics)

    topic = await topics.create(conn, uuid4(), "digest", "Digest", None)
    user_id = uuid4()
    created, _ = await service.subscribe(conn, user_id, topic.id)

    updated = await service.update_subscription(
        conn=conn,
        user_id=user_id,
        subscription_id=created.id,
        is_active=None,
        preferences_patch=SubscriptionPreferencesPatchRequest(
            quiet_hours=QuietHoursPatchRequest(start=time(0, 0, 0), end=time(0, 0, 0)),
        ),
    )

    assert updated.preferences.quiet_hours_start is None
    assert updated.preferences.quiet_hours_end is None


@pytest.mark.asyncio
async def test_update_preferences_rejects_invalid_timezone():
    conn = FakeConnection()
    topics = FakeTopicsRepository()
    subscriptions = FakeSubscriptionsRepository()
    service = SubscriptionsService(subscriptions, topics)

    topic = await topics.create(conn, uuid4(), "system", "System", None)
    user_id = uuid4()
    created, _ = await service.subscribe(conn, user_id, topic.id)

    with pytest.raises(ValidationError):
        await service.update_subscription(
            conn=conn,
            user_id=user_id,
            subscription_id=created.id,
            is_active=None,
            preferences_patch=SubscriptionPreferencesPatchRequest(timezone="Mars/Phobos"),
        )


@pytest.mark.asyncio
async def test_update_preferences_rejects_empty_channels():
    conn = FakeConnection()
    topics = FakeTopicsRepository()
    subscriptions = FakeSubscriptionsRepository()
    service = SubscriptionsService(subscriptions, topics)

    topic = await topics.create(conn, uuid4(), "ops", "Ops", None)
    user_id = uuid4()
    created, _ = await service.subscribe(conn, user_id, topic.id)

    with pytest.raises(PydanticValidationError):
        SubscriptionPreferencesPatchRequest(channels=[])

    # Keep service call to ensure baseline path still works with valid patch.
    updated = await service.update_subscription(
        conn=conn,
        user_id=user_id,
        subscription_id=created.id,
        is_active=None,
        preferences_patch=SubscriptionPreferencesPatchRequest(channels=["web"]),
    )
    assert updated.preferences.channels == ["web"]
