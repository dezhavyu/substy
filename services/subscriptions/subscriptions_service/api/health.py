from fastapi import APIRouter, Depends

from subscriptions_service.core.dependencies import get_db
from subscriptions_service.infrastructure.db import Database
from subscriptions_service.schemas.common import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def ready(db: Database = Depends(get_db)) -> ReadinessResponse:
    try:
        await db.ping()
        return ReadinessResponse(status="ok", database="up")
    except Exception:
        return ReadinessResponse(status="degraded", database="down")
