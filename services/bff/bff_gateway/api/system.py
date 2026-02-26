from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from bff_gateway.core.dependencies import get_clients, get_metrics, get_redis
from bff_gateway.observability.metrics import MetricsRegistry

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(redis=Depends(get_redis)) -> dict[str, str]:
    # Only Redis is required in readiness to avoid coupling gateway health to all downstream services.
    try:
        await redis.ping()
        return {"status": "ok", "redis": "up"}
    except Exception:
        return {"status": "degraded", "redis": "down"}


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(metrics_registry: MetricsRegistry = Depends(get_metrics)) -> str:
    return metrics_registry.render_prometheus()
