import json
from typing import Any


def payload_size_bytes(payload: dict[str, Any]) -> int:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return len(raw)


def payload_depth(value: Any, current_depth: int = 0) -> int:
    if isinstance(value, dict):
        if not value:
            return current_depth + 1
        return max(payload_depth(v, current_depth + 1) for v in value.values())
    if isinstance(value, list):
        if not value:
            return current_depth + 1
        return max(payload_depth(v, current_depth + 1) for v in value)
    return current_depth + 1
