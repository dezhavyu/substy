from datetime import datetime, timezone
from uuid import UUID, uuid4

import asyncpg

from notifications_service.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from notifications_service.core.metrics import MetricsRegistry
from notifications_service.core.pagination import decode_cursor, notifications_cursor
from notifications_service.core.payload import payload_depth, payload_size_bytes
from notifications_service.core.settings import Settings
from notifications_service.repositories.notifications import NotificationsRepository
from notifications_service.repositories.outbox import OutboxRepository
from notifications_service.repositories.records import NotificationRecord


class NotificationsService:
    _allowed_status_filters = {"created", "scheduled", "queued", "cancelled"}

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

    async def create_notification(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        topic_id: UUID,
        payload: dict,
        scheduled_at: datetime | None,
        idempotency_key: str | None,
        request_id: str,
    ) -> tuple[NotificationRecord, bool]:
        self._validate_payload(payload)
        normalized_scheduled_at = self._normalize_scheduled_at(scheduled_at)

        if idempotency_key:
            existing = await self._notifications.get_by_idempotency_key(conn, user_id, idempotency_key)
            if existing:
                return existing, False

        notification_id = uuid4()
        event_id = uuid4()

        status = "created" if self._is_immediate(normalized_scheduled_at) else "scheduled"

        try:
            async with conn.transaction():
                notification = await self._notifications.create(
                    conn=conn,
                    notification_id=notification_id,
                    topic_id=topic_id,
                    payload=payload,
                    scheduled_at=normalized_scheduled_at,
                    created_by=user_id,
                    idempotency_key=idempotency_key,
                    status=status,
                )

                if notification.status == "created":
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
                            "scheduled_at": notification.scheduled_at.isoformat() if notification.scheduled_at else None,
                            "created_at": notification.created_at.isoformat(),
                        },
                        headers={
                            "request_id": request_id,
                            "user_id": str(user_id),
                        },
                    )

            self._metrics.inc_notifications_created()
            return notification, True
        except asyncpg.PostgresError as exc:
            if exc.sqlstate == "23505" and idempotency_key:
                existing = await self._notifications.get_by_idempotency_key(conn, user_id, idempotency_key)
                if existing:
                    return existing, False
            raise

    async def get_notification(
        self,
        conn: asyncpg.Connection,
        notification_id: UUID,
        user_id: UUID,
        roles: set[str],
    ) -> NotificationRecord:
        notification = await self._notifications.get_by_id(conn, notification_id)
        if notification is None:
            raise NotFoundError("Notification not found")

        if notification.created_by != user_id and "admin" not in roles:
            raise ForbiddenError()

        return notification

    async def cancel_notification(
        self,
        conn: asyncpg.Connection,
        notification_id: UUID,
        user_id: UUID,
        roles: set[str],
    ) -> NotificationRecord:
        notification = await self.get_notification(
            conn=conn,
            notification_id=notification_id,
            user_id=user_id,
            roles=roles,
        )

        if notification.status != "scheduled":
            raise ConflictError("Only scheduled notifications can be cancelled")

        cancelled = await self._notifications.cancel_if_scheduled(conn, notification_id)
        if cancelled is None:
            raise ConflictError("Notification is not scheduled")
        return cancelled

    async def list_my_notifications(
        self,
        conn: asyncpg.Connection,
        user_id: UUID,
        limit: int,
        cursor: str | None,
        status: str | None,
        topic_id: UUID | None,
    ) -> tuple[list[NotificationRecord], str | None]:
        if status is not None and status not in self._allowed_status_filters:
            raise ValidationError("Invalid status filter")

        cursor_data = decode_cursor(cursor)
        created_at: datetime | None = None
        notification_id: UUID | None = None

        if cursor_data:
            try:
                created_at = datetime.fromisoformat(cursor_data["created_at"])
                notification_id = UUID(cursor_data["id"])
            except (KeyError, ValueError) as exc:
                raise ValidationError("Invalid cursor") from exc

        rows = await self._notifications.list_by_user(
            conn=conn,
            created_by=user_id,
            limit=limit + 1,
            cursor_created_at=created_at,
            cursor_id=notification_id,
            status=status,
            topic_id=topic_id,
        )

        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = notifications_cursor(last.created_at, last.id)

        return rows, next_cursor

    def _validate_payload(self, payload: dict) -> None:
        size = payload_size_bytes(payload)
        if size > self._settings.payload_max_bytes:
            raise ValidationError("Payload is too large")

        depth = payload_depth(payload)
        if depth > self._settings.payload_max_depth:
            raise ValidationError("Payload is too deep")

    @staticmethod
    def _normalize_scheduled_at(scheduled_at: datetime | None) -> datetime | None:
        if scheduled_at is None:
            return None
        if scheduled_at.tzinfo is None or scheduled_at.tzinfo.utcoffset(scheduled_at) is None:
            raise ValidationError("scheduled_at must include timezone")
        return scheduled_at.astimezone(timezone.utc)

    @staticmethod
    def _is_immediate(scheduled_at: datetime | None) -> bool:
        if scheduled_at is None:
            return True
        return scheduled_at <= datetime.now(timezone.utc)
