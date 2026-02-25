class AuthServiceError(Exception):
    message = "Service error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class ValidationError(AuthServiceError):
    message = "Validation error"


class AuthenticationError(AuthServiceError):
    message = "Invalid credentials"


class AuthorizationError(AuthServiceError):
    message = "Not authorized"


class RateLimitExceededError(AuthServiceError):
    message = "Too many requests"


class UserAlreadyExistsError(AuthServiceError):
    message = "Registration accepted"


class SessionNotFoundError(AuthServiceError):
    message = "Session not found"
