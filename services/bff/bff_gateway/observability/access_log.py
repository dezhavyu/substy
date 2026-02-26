import time

from fastapi import Request
from opentelemetry.trace import get_current_span
from starlette.middleware.base import BaseHTTPMiddleware


class AccessLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, logger):  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._logger = logger

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        started = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - started

        route = request.url.path
        status = response.status_code
        metrics = getattr(request.app.state, "metrics", None)
        if metrics:
            metrics.observe_http(route, status, duration)

        span_ctx = get_current_span().get_span_context()
        trace_id = format(span_ctx.trace_id, "032x") if span_ctx and span_ctx.trace_id else ""

        self._logger.info(
            "request.completed",
            request_id=getattr(request.state, "request_id", ""),
            trace_id=trace_id,
            method=request.method,
            path=route,
            status_code=status,
            latency_ms=round(duration * 1000, 2),
            user_id=getattr(request.state, "user_id", ""),
        )
        return response
