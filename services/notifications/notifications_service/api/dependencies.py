from fastapi import Depends

from notifications_service.core.dependencies import get_metrics
from notifications_service.core.metrics import MetricsRegistry
from notifications_service.core.settings import Settings, get_settings
from notifications_service.repositories.notifications import NotificationsRepository
from notifications_service.repositories.outbox import OutboxRepository
from notifications_service.services.notifications import NotificationsService


def get_notifications_service(
    settings: Settings = Depends(get_settings),
    metrics: MetricsRegistry = Depends(get_metrics),
) -> NotificationsService:
    return NotificationsService(
        notifications_repository=NotificationsRepository(),
        outbox_repository=OutboxRepository(),
        settings=settings,
        metrics=metrics,
    )
