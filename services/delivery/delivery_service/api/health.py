from fastapi import APIRouter, Depends

from delivery_service.core.container import Container
from delivery_service.core.dependencies import get_container
from delivery_service.schemas.common import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def ready(container: Container = Depends(get_container)) -> ReadinessResponse:
    db_status = "down"
    redis_status = "down"
    nats_status = "down"

    try:
        await container.db.ping()
        db_status = "up"
    except Exception:
        db_status = "down"

    try:
        await container.redis.ping()
        redis_status = "up"
    except Exception:
        redis_status = "down"

    try:
        await container.nats.ping()
        nats_status = "up"
    except Exception:
        nats_status = "down"

    status = "ok" if db_status == redis_status == nats_status == "up" else "degraded"
    return ReadinessResponse(status=status, database=db_status, redis=redis_status, nats=nats_status)
