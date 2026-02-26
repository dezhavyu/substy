from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(slots=True)
class DeliveryResult:
    success: bool
    error_code: str | None = None
    error_message: str | None = None


class DeliveryProvider(Protocol):
    async def send(self, user_id: UUID, payload: dict) -> DeliveryResult:
        ...
