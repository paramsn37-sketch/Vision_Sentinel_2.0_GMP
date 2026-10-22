"""Single-admin authentication: argon2 password hash, signed session cookie, double-submit CSRF token."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

SESSION_COOKIE = "vs_session"
CSRF_COOKIE = "vs_csrf"
CSRF_HEADER = "x-csrf-token"
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False


class Signer:
    def __init__(self, secret: str) -> None:
        self._key = secret.encode()

    def _mac(self, payload: bytes) -> str:
        return (
            base64.urlsafe_b64encode(hmac.new(self._key, payload, hashlib.sha256).digest())
            .decode()
            .rstrip("=")
        )

    def dumps(self, data: dict, ttl_s: int) -> str:
        body = dict(data, exp=int(time.time()) + ttl_s)
        payload = (
            base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode()).decode().rstrip("=")
        )
        return f"{payload}.{self._mac(payload.encode())}"

    def loads(self, token: str) -> dict | None:
        try:
            payload, mac = token.rsplit(".", 1)
        except ValueError:
            return None
        if not hmac.compare_digest(mac, self._mac(payload.encode())):
            return None
        try:
            body = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        except (ValueError, json.JSONDecodeError):
            return None
        return body if body.get("exp", 0) > time.time() else None


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


class RateLimiter:
    """Sliding window: at most `limit` attempts per `window_s` per key (client IP)."""

    def __init__(self, limit: int = 5, window_s: float = 60.0) -> None:
        self.limit, self.window_s = limit, window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window_s:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True
