from fastapi import APIRouter, Depends

from notifications_service.core.dependencies import get_db, get_nats
from notifications_service.infrastructure.db import Database
from notifications_service.infrastructure.nats_client import NATSClient
from notifications_service.schemas.common import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(
    db: Database = Depends(get_db),
    nats_client: NATSClient = Depends(get_nats),
) -> ReadinessResponse:
    db_status = "down"
    nats_status = "down"

    try:
        await db.ping()
        db_status = "up"
    except Exception:
        db_status = "down"

    try:
        await nats_client.ping()
        nats_status = "up"
    except Exception:
        nats_status = "down"

    status = "ok" if db_status == "up" and nats_status == "up" else "degraded"
    return ReadinessResponse(status=status, database=db_status, nats=nats_status)
