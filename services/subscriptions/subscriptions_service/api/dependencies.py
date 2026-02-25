from subscriptions_service.repositories.subscriptions import SubscriptionsRepository
from subscriptions_service.repositories.topics import TopicsRepository
from subscriptions_service.services.subscriptions import SubscriptionsService
from subscriptions_service.services.topics import TopicsService


def get_topics_service() -> TopicsService:
    return TopicsService(topics_repository=TopicsRepository())


def get_subscriptions_service() -> SubscriptionsService:
    topics_repository = TopicsRepository()
    return SubscriptionsService(
        subscriptions_repository=SubscriptionsRepository(),
        topics_repository=topics_repository,
    )
