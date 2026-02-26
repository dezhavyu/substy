import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from delivery_service.core.exceptions import AppError

logger = logging.getLogger(__name__)


def _payload(request: Request, code: str, message: str) -> dict[str, str]:
    return {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", ""),
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_payload(request, exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content=_payload(request, "validation_error", "Invalid request"))

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(status_code=500, content=_payload(request, "internal_error", "Internal server error"))
