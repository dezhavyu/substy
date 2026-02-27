import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


class PasswordManager:
    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash_password(self, plain_password: str) -> str:
        return self._hasher.hash(plain_password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return self._hasher.verify(hashed_password, plain_password)
        except VerifyMismatchError:
            return False


class RefreshTokenManager:
    def __init__(self, pepper: str) -> None:
        self._pepper = pepper

    def generate_token(self) -> str:
        return secrets.token_urlsafe(64)

    def hash_token(self, token: str) -> str:
        payload = f"{token}:{self._pepper}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def expires_at(ttl_seconds: int) -> datetime:
        return datetime.now(tz=timezone.utc) + timedelta(seconds=ttl_seconds)
