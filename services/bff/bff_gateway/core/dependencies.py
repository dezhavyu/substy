from fastapi import Request

from bff_gateway.clients.downstream import ServiceClients
from bff_gateway.observability.metrics import MetricsRegistry


def get_clients(request: Request) -> ServiceClients:
    return request.app.state.clients


def get_redis(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.redis


def get_metrics(request: Request) -> MetricsRegistry:
    return request.app.state.metrics
