from collections.abc import AsyncIterator
from uuid import UUID

from delivery_service.infrastructure.http_client import SubscriptionsClient
from delivery_service.schemas.subscriptions import SubscriberItem, SubscribersPage


class SubscriptionsFetcherService:
    def __init__(self, subscriptions_client: SubscriptionsClient) -> None:
        self._client = subscriptions_client

    async def iter_subscribers(self, topic_id: UUID) -> AsyncIterator[SubscriberItem]:
        cursor: str | None = None

        while True:
            raw = await self._client.fetch_subscribers_page(str(topic_id), cursor)
            page = SubscribersPage.model_validate(raw)

            for item in page.items:
                yield item

            if not page.next_cursor:
                break
            cursor = page.next_cursor
