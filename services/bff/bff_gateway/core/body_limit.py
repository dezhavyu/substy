from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body_bytes: int):  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self._max_body_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "code": "payload_too_large",
                    "message": "Request body is too large",
                    "request_id": getattr(request.state, "request_id", ""),
                },
            )

        body = await request.body()
        if len(body) > self._max_body_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "code": "payload_too_large",
                    "message": "Request body is too large",
                    "request_id": getattr(request.state, "request_id", ""),
                },
            )

        request.state.cached_body = body
        return await call_next(request)
