import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from delivery_service.core.metrics import MetricsRegistry
from delivery_service.core.settings import Settings


class SubscriptionsClient:
    def __init__(self, settings: Settings, metrics: MetricsRegistry) -> None:
        self._settings = settings
        self._metrics = metrics
        self._client: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0), limits=httpx.Limits(max_connections=20))

    async def shutdown(self) -> None:
        if self._client:
            await self._client.aclose()

    async def fetch_subscribers_page(self, topic_id: str, cursor: str | None) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("HTTP client is not initialized")

        params: dict[str, Any] = {"limit": self._settings.subscriptions_page_limit}
        if cursor:
            params["cursor"] = cursor

        started = time.perf_counter()
        response = await self._client.get(
            f"{self._settings.subscriptions_internal_url}/internal/topics/{topic_id}/subscribers",
            params=params,
        )
        elapsed = time.perf_counter() - started
        self._metrics.observe_subscriptions_fetch_latency(elapsed)

        response.raise_for_status()
        return response.json()
