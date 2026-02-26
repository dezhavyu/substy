from uuid import UUID

from arq.connections import ArqRedis, RedisSettings, create_pool

from delivery_service.core.container import Container, build_container, shutdown_container
from delivery_service.core.settings import get_settings
from delivery_service.providers.factory import build_providers
from delivery_service.repositories.delivery_attempts import DeliveryAttemptsRepository
from delivery_service.services.delivery_executor import DeliveryExecutorService


async def startup(ctx: dict) -> None:  # type: ignore[no-untyped-def]
    settings = get_settings()
    container = await build_container(settings)
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))

    ctx["settings"] = settings
    ctx["container"] = container
    ctx["redis"] = redis
    ctx["executor"] = DeliveryExecutorService(
        settings=settings,
        attempts_repository=DeliveryAttemptsRepository(),
        providers=build_providers(settings),
        nats_client=container.nats,
        metrics=container.metrics,
    )


async def shutdown(ctx: dict) -> None:  # type: ignore[no-untyped-def]
    redis: ArqRedis = ctx["redis"]
    await redis.aclose()

    container: Container = ctx["container"]
    await shutdown_container(container)


async def _send_channel(ctx: dict, attempt_id: str) -> None:  # type: ignore[no-untyped-def]
    container: Container = ctx["container"]
    redis: ArqRedis = ctx["redis"]
    executor: DeliveryExecutorService = ctx["executor"]

    async for conn in container.db.connection():
        await executor.execute_send(conn=conn, redis=redis, attempt_id=UUID(attempt_id))


async def send_push(ctx: dict, attempt_id: str) -> None:  # type: ignore[no-untyped-def]
    await _send_channel(ctx, attempt_id)


async def send_email(ctx: dict, attempt_id: str) -> None:  # type: ignore[no-untyped-def]
    await _send_channel(ctx, attempt_id)


async def send_web(ctx: dict, attempt_id: str) -> None:  # type: ignore[no-untyped-def]
    await _send_channel(ctx, attempt_id)


async def retry_attempt(ctx: dict, attempt_id: str, channel: str) -> None:  # type: ignore[no-untyped-def]
    redis: ArqRedis = ctx["redis"]
    await redis.enqueue_job(f"send_{channel}", attempt_id)


class WorkerSettings:
    functions = [send_push, send_email, send_web, retry_attempt]
    on_startup = startup
    on_shutdown = shutdown
