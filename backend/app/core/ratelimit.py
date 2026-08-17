"""In-memory sliding-window rate limiter (per client IP)."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.config import settings


class RateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit = limit_per_minute
        self.hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        now = time.time()
        window = 60.0
        with self._lock:
            q = self.hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= self.limit:
                retry = int(window - (now - q[0])) + 1
                return False, retry
            q.append(now)
            return True, 0

    def reset(self, key: str) -> None:
        with self._lock:
            self.hits.pop(key, None)


limiter = RateLimiter(settings.RATE_LIMIT_PER_MINUTE)
