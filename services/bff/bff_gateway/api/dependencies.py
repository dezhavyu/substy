from fastapi import Depends, Request
from redis.asyncio import Redis

from bff_gateway.clients.downstream import ServiceClients
from bff_gateway.core.errors import RateLimitError, ServiceUnavailableError
from bff_gateway.core.settings import Settings, get_settings
from bff_gateway.observability.metrics import MetricsRegistry
from bff_gateway.rate_limit.limiter import RedisRateLimiter
from bff_gateway.security.deps import get_current_identity


def get_clients(request: Request) -> ServiceClients:
    return request.app.state.clients


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_metrics(request: Request) -> MetricsRegistry:
    return request.app.state.metrics


async def rate_limit_auth(
    request: Request,
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis),
    metrics: MetricsRegistry = Depends(get_metrics),
) -> None:
    limiter = RedisRateLimiter(redis)
    client_ip = request.headers.get("x-forwarded-for", "") or (request.client.host if request.client else "unknown")
    key = f"bff:rate:auth:{request.url.path}:{client_ip}"

    try:
        allowed = await limiter.is_allowed(key, settings.rate_limit_auth_per_minute)
    except Exception as exc:
        metrics.inc_rate_limited()
        raise ServiceUnavailableError("Rate limiter unavailable") from exc

    if not allowed:
        metrics.inc_rate_limited()
        raise RateLimitError()


async def rate_limit_user(
    request: Request,
    identity=Depends(get_current_identity),
    settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis),
    metrics: MetricsRegistry = Depends(get_metrics),
):
    limiter = RedisRateLimiter(redis)
    key = f"bff:rate:user:{identity.user_id}"

    try:
        allowed = await limiter.is_allowed(key, settings.rate_limit_user_per_minute)
    except Exception:
        # fail-open for non-auth endpoints
        return identity

    if not allowed:
        metrics.inc_rate_limited()
        raise RateLimitError()

    return identity
