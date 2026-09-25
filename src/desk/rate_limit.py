from __future__ import annotations

import threading
import time


class RequestRateLimiter:
    def __init__(self, weights_per_second: float = 30.0, capacity: float | None = None):
        self.rate = max(weights_per_second, 1.0)
        self.capacity = max(capacity or self.rate, 1.0)
        self.tokens = self.capacity
        self.updated = time.monotonic()
        self.lock = threading.Lock()

    def wait(self, weight: float = 1.0) -> None:
        weight = max(weight, 0.0)
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= weight:
                    self.tokens -= weight
                    return
                delay = (weight - self.tokens) / self.rate
            time.sleep(delay)


REQUEST_LIMITER = RequestRateLimiter()
