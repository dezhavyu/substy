from dataclasses import dataclass
from uuid import uuid4

import asyncpg
from opentelemetry import trace

from notifications_service.core.metrics import MetricsRegistry
from notifications_service.core.settings import Settings
from notifications_service.repositories.notifications import NotificationsRepository
from notifications_service.repositories.outbox import OutboxRepository


@dataclass(slots=True)
class SchedulerTickResult:
    picked_count: int
    due_count: int
    backlog_count: int


class SchedulerService:
    def __init__(
        self,
        notifications_repository: NotificationsRepository,
        outbox_repository: OutboxRepository,
        settings: Settings,
        metrics: MetricsRegistry,
    ) -> None:
        self._notifications = notifications_repository
        self._outbox = outbox_repository
        self._settings = settings
        self._metrics = metrics
        self._tracer = trace.get_tracer(__name__)

    async def run_one_tick(
        self,
        conn: asyncpg.Connection,
        request_id: str = "scheduler",
    ) -> SchedulerTickResult:
        tick_timer = self._metrics.start_timer()

        with self._tracer.start_as_current_span("scheduler.tick"):
            with self._tracer.start_as_current_span("scheduler.tick.transaction"):
                async with conn.transaction():
                    due = await self._notifications.lock_due_scheduled_batch(
                        conn=conn,
                        limit=self._settings.scheduler_batch_size,
                    )

                    queued = await self._notifications.mark_queued_by_ids(
                        conn=conn,
                        notification_ids=[row.id for row in due],
                    )

                    for notification in queued:
                        event_id = uuid4()
                        await self._outbox.create_event(
                            conn=conn,
                            event_id=event_id,
                            aggregate_type="notification",
                            aggregate_id=notification.id,
                            event_type="notification.created.v1",
                            payload={
                                "event_id": str(event_id),
                                "notification_id": str(notification.id),
                                "topic_id": str(notification.topic_id),
                                "created_by": str(notification.created_by),
                                "payload": notification.payload,
                                "scheduled_at": notification.scheduled_at.isoformat()
                                if notification.scheduled_at
                                else None,
                                "created_at": notification.created_at.isoformat(),
                            },
                            headers={
                                "request_id": request_id,
                                "user_id": str(notification.created_by),
                                "source": "notifications-scheduler",
                            },
                        )

            backlog_count = await self._notifications.count_scheduled_backlog(conn)
            due_count = await self._notifications.count_scheduled_due(conn)

        picked_count = len(queued)
        self._metrics.inc_scheduler_picked(picked_count)
        self._metrics.set_scheduled_counts(backlog_count=backlog_count, due_count=due_count)
        self._metrics.observe_scheduler_tick_duration(tick_timer)

        return SchedulerTickResult(
            picked_count=picked_count,
            due_count=due_count,
            backlog_count=backlog_count,
        )
