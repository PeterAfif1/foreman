"""Password login for the dashboard and API.

One shared password for the people who review leads. The database holds
customers' names and phone numbers, so nothing except the login page and the
health check is served without it.
"""

import hmac
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from dotenv import load_dotenv

PUBLIC_PATHS = {"/login", "/health", "/favicon.svg"}
MAX_FAILURES = 5
LOCKOUT_SECONDS = 15 * 60
SESSION_DAYS = 30


@dataclass(frozen=True)
class AuthSettings:
    enabled: bool
    password: str = ""
    secret_key: str = "dev-only-not-secret"
    secure_cookies: bool = False


def load_settings() -> AuthSettings:
    """Login is on unless FOREMAN_AUTH=off is set explicitly. Forgetting to
    configure a password fails at startup instead of serving leads to anyone."""
    load_dotenv()
    if os.getenv("FOREMAN_AUTH", "on").lower() == "off":
        return AuthSettings(enabled=False)
    password = os.getenv("FOREMAN_PASSWORD", "")
    secret_key = os.getenv("FOREMAN_SECRET_KEY", "")
    if not password or not secret_key:
        raise RuntimeError(
            "Set FOREMAN_PASSWORD and FOREMAN_SECRET_KEY, "
            "or FOREMAN_AUTH=off for local development only."
        )
    if len(password) < 12:
        raise RuntimeError("FOREMAN_PASSWORD must be at least 12 characters.")
    return AuthSettings(
        enabled=True,
        password=password,
        secret_key=secret_key,
        secure_cookies=os.getenv("FOREMAN_SECURE_COOKIES", "on").lower() != "off",
    )


def password_matches(given: str, expected: str) -> bool:
    # Constant-time compare, so response timing doesn't leak how much matched.
    return hmac.compare_digest(given.encode(), expected.encode())


class LoginLimiter:
    """Locks an address out after too many wrong passwords in a row."""

    def __init__(self, max_failures: int = MAX_FAILURES, window: int = LOCKOUT_SECONDS):
        self.max_failures = max_failures
        self.window = window
        self.failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> deque[float]:
        q = self.failures[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def locked(self, key: str, now: float | None = None) -> bool:
        return len(self._prune(key, now or time.monotonic())) >= self.max_failures

    def fail(self, key: str, now: float | None = None) -> None:
        now = now or time.monotonic()
        self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        self.failures.pop(key, None)
