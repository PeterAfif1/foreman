"""Limits for the public chat, so a bot can't run up the OpenAI bill.

In memory: limits reset when the server restarts, which is fine for one small
server. Several servers would need a shared store (Redis) instead.
"""

import time
from collections import defaultdict, deque


class RateLimiter:
    """At most `limit` events per key in any `window` seconds."""

    def __init__(self, limit: int, window: float):
        self.limit = limit
        self.window = window
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = now if now is not None else time.monotonic()
        q = self.events[key]
        while q and now - q[0] >= self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


class ChatLimits:
    def __init__(
        self,
        messages_per_10_min: int = 30,
        chats_per_hour: int = 5,
        chats_per_day: int = 200,
    ):
        self.messages = RateLimiter(messages_per_10_min, 600)
        self.new_chats = RateLimiter(chats_per_hour, 3600)
        self.daily = RateLimiter(chats_per_day, 86400)
