from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class User:
    id: UUID
    email: str
    password_hash: str
    is_active: bool
    created_at: datetime


@dataclass(slots=True)
class Session:
    id: UUID
    user_id: UUID
    token_hash: str
    user_agent: str | None
    ip_address: str | None
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime
