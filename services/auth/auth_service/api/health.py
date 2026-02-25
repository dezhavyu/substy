from fastapi import APIRouter, Depends

from auth_service.api.dependencies import get_infrastructure
from auth_service.infrastructure.containers import Infrastructure
from auth_service.schemas.common import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(infrastructure: Infrastructure = Depends(get_infrastructure)) -> ReadinessResponse:
    db_status = "down"
    redis_status = "down"
    nats_status = "down"

    try:
        if infrastructure.db_pool:
            async with infrastructure.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                db_status = "up"
    except Exception:
        db_status = "down"

    try:
        if infrastructure.redis:
            await infrastructure.redis.ping()
            redis_status = "up"
    except Exception:
        redis_status = "down"

    if infrastructure.nats_client and infrastructure.nats_client.is_connected:
        nats_status = "up"

    status = "ok" if db_status == redis_status == nats_status == "up" else "degraded"
    return ReadinessResponse(status=status, database=db_status, redis=redis_status, nats=nats_status)
