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
    message = "Resource not found"
    status_code = 404


class ConflictError(AppError):
    code = "conflict"
    message = "Conflict"
    status_code = 409


class ValidationError(AppError):
    code = "validation_error"
    message = "Validation error"
    status_code = 422
