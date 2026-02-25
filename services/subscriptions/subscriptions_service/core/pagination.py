import base64
import json
from datetime import datetime
from uuid import UUID

from subscriptions_service.core.exceptions import ValidationError


def encode_cursor(payload: dict[str, str]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def decode_cursor(cursor: str | None) -> dict[str, str] | None:
    if not cursor:
        return None
    try:
        data = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        payload = json.loads(data)
    except Exception as exc:
        raise ValidationError("Invalid cursor") from exc

    if not isinstance(payload, dict):
        raise ValidationError("Invalid cursor")

    return {str(k): str(v) for k, v in payload.items()}


def topic_cursor(created_at: datetime, topic_id: UUID) -> str:
    return encode_cursor({"created_at": created_at.isoformat(), "id": str(topic_id)})


def subscriptions_cursor(created_at: datetime, subscription_id: UUID) -> str:
    return encode_cursor({"created_at": created_at.isoformat(), "id": str(subscription_id)})


def subscribers_cursor(user_id: UUID, subscription_id: UUID) -> str:
    return encode_cursor({"user_id": str(user_id), "id": str(subscription_id)})
