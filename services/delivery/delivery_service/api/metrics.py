from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from delivery_service.core.container import Container
from delivery_service.core.dependencies import get_container

router = APIRouter(tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(container: Container = Depends(get_container)) -> str:
    return container.metrics.render_prometheus()
