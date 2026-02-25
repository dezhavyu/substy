from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from subscriptions_service.core.exceptions import ForbiddenError, NotFoundError
from subscriptions_service.repositories.records import SubscriberRecord, SubscriptionRecord, TopicRecord
from subscriptions_service.services.subscriptions import SubscriptionsService
from subscriptions_service.services.topics import TopicsService


class FakeTopicsRepository:
    def __init__(self) -> None:
        self.topics: dict[UUID, TopicRecord] = {}

    async def create(self, conn, topic_id, key, name, description):
        topic = TopicRecord(
            id=topic_id,
            key=key,
            name=name,
            description=description,
            created_at=datetime.now(timezone.utc),
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
        row = SubscriptionRecord(
            id=subscription_id,
            user_id=user_id,
            topic_id=topic_id,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
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
        row.updated_at = datetime.now(timezone.utc)
        return row

    async def list_active_subscribers(self, conn, topic_id, limit, cursor_user_id, cursor_subscription_id):
        rows = [x for x in self.rows.values() if x.topic_id == topic_id and x.is_active]
        rows.sort(key=lambda x: (x.user_id, x.id))
        return [SubscriberRecord(user_id=x.user_id, subscription_id=x.id) for x in rows[:limit]]


@pytest.mark.asyncio
async def test_subscribe_is_idempotent():
    topics = FakeTopicsRepository()
    subscriptions = FakeSubscriptionsRepository()

    topic = await topics.create(None, uuid4(), "news", "News", None)
    service = SubscriptionsService(subscriptions, topics)

    user_id = uuid4()
    first, created1 = await service.subscribe(None, user_id, topic.id)
    second, created2 = await service.subscribe(None, user_id, topic.id)

    assert created1 is True
    assert created2 is False
    assert first.id == second.id


@pytest.mark.asyncio
async def test_create_topic_requires_admin_role():
    service = TopicsService(FakeTopicsRepository())

    with pytest.raises(ForbiddenError):
        await service.create_topic(None, roles={"user"}, key="news", name="News", description=None)


@pytest.mark.asyncio
async def test_unsubscribe_missing_subscription_raises_not_found():
    topics = FakeTopicsRepository()
    subscriptions = FakeSubscriptionsRepository()
    service = SubscriptionsService(subscriptions, topics)

    with pytest.raises(NotFoundError):
        await service.unsubscribe(None, user_id=uuid4(), subscription_id=uuid4())
