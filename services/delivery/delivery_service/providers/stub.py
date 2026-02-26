import random
from uuid import UUID

from delivery_service.providers.base import DeliveryProvider, DeliveryResult


class _BaseStubProvider(DeliveryProvider):
    def __init__(self, fail_rate: float) -> None:
        self._fail_rate = max(0.0, min(1.0, fail_rate))

    async def send(self, user_id: UUID, payload: dict) -> DeliveryResult:
        if random.random() < self._fail_rate:
            return DeliveryResult(success=False, error_code="stub_error", error_message="Stub provider failure")
        return DeliveryResult(success=True)


class StubPushProvider(_BaseStubProvider):
    pass


class StubEmailProvider(_BaseStubProvider):
    pass


class StubWebProvider(_BaseStubProvider):
    pass
