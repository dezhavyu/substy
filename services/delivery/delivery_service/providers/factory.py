from delivery_service.core.settings import Settings
from delivery_service.providers.base import DeliveryProvider
from delivery_service.providers.stub import StubEmailProvider, StubPushProvider, StubWebProvider


def build_providers(settings: Settings) -> dict[str, DeliveryProvider]:
    return {
        "push": StubPushProvider(settings.provider_stub_fail_rate),
        "email": StubEmailProvider(settings.provider_stub_fail_rate),
        "web": StubWebProvider(settings.provider_stub_fail_rate),
    }
