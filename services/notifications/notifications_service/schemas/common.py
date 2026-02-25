from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    nats: str
