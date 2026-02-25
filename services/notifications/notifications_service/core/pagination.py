import base64
import json
from datetime import datetime
from uuid import UUID

from notifications_service.core.exceptions import ValidationError


def encode_cursor(payload: dict[str, str]) -> str:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(data).decode("utf-8")


def decode_cursor(cursor: str | None) -> dict[str, str] | None:
    if not cursor:
        return None

    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        data = json.loads(raw)
    except Exception as exc:
        raise ValidationError("Invalid cursor") from exc

    if not isinstance(data, dict):
        raise ValidationError("Invalid cursor")

    return {str(k): str(v) for k, v in data.items()}


def notifications_cursor(created_at: datetime, notification_id: UUID) -> str:
    return encode_cursor({"created_at": created_at.isoformat(), "id": str(notification_id)})
