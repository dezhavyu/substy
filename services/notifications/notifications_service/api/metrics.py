from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from notifications_service.core.dependencies import get_metrics
from notifications_service.core.metrics import MetricsRegistry

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(metrics_registry: MetricsRegistry = Depends(get_metrics)) -> str:
    return metrics_registry.render_prometheus()
