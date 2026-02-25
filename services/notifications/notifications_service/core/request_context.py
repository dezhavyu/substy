import uuid
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id

        token = request_id_ctx_var.set(request_id)
        try:
            response: Response = await call_next(request)
        finally:
            request_id_ctx_var.reset(token)

        response.headers["x-request-id"] = request_id
        return response
