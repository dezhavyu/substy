import asyncio
import random
from dataclasses import dataclass

import httpx
from opentelemetry.propagate import inject

from bff_gateway.core.errors import UpstreamError
from bff_gateway.core.settings import Settings


@dataclass(slots=True)
class ServiceClients:
    auth: httpx.AsyncClient
    subscriptions: httpx.AsyncClient
    notifications: httpx.AsyncClient

    async def aclose(self) -> None:
        await self.auth.aclose()
        await self.subscriptions.aclose()
        await self.notifications.aclose()


def build_service_clients(settings: Settings) -> ServiceClients:
    timeout = httpx.Timeout(
        connect=settings.http_connect_timeout_seconds,
        read=settings.http_read_timeout_seconds,
        write=settings.http_read_timeout_seconds,
        pool=settings.http_read_timeout_seconds,
    )

    return ServiceClients(
        auth=httpx.AsyncClient(base_url=settings.auth_service_url, timeout=timeout),
        subscriptions=httpx.AsyncClient(base_url=settings.subscriptions_service_url, timeout=timeout),
        notifications=httpx.AsyncClient(base_url=settings.notifications_service_url, timeout=timeout),
    )


async def send_with_retries(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    params,
    headers,
    content,
    retries_get: int,
    service_name: str,
):
    headers_copy = dict(headers)
    inject(headers_copy)

    attempts = retries_get + 1 if method.upper() == "GET" else 1
    last_exc: Exception | None = None

    for attempt in range(attempts):
        try:
            return await client.request(
                method=method,
                url=path,
                params=params,
                headers=headers_copy,
                content=content,
            )
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            last_exc = exc
            if attempt == attempts - 1:
                break
            await asyncio.sleep(random.uniform(0.05, 0.25))

    raise UpstreamError(f"{service_name} is unavailable") from last_exc
