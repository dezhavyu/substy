class AppError(Exception):
    code = "app_error"
    message = "Application error"
    status_code = 400

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class UnauthorizedError(AppError):
    code = "unauthorized"
    message = "Unauthorized"
    status_code = 401


class ForbiddenError(AppError):
    code = "forbidden"
    message = "Forbidden"
    status_code = 403


class NotFoundError(AppError):
    code = "not_found"
    message = "Not found"
    status_code = 404


class ValidationError(AppError):
    code = "validation_error"
    message = "Validation error"
    status_code = 422


class UpstreamError(AppError):
    code = "upstream_error"
    message = "Upstream service failed"
    status_code = 502


class RateLimitError(AppError):
    code = "rate_limited"
    message = "Too many requests"
    status_code = 429


class ServiceUnavailableError(AppError):
    code = "service_unavailable"
    message = "Service unavailable"
    status_code = 503
