from __future__ import annotations

import math
import time
from dataclasses import dataclass


@dataclass
class TokenBucket:
    capacity: int
    refill_rate: float
    tokens: float
    updated_at: float

    @classmethod
    def create(cls, requests_per_minute: int) -> TokenBucket:
        now = time.monotonic()
        return cls(requests_per_minute, requests_per_minute / 60.0, requests_per_minute, now)

    def consume(self, now: float | None = None) -> tuple[bool, int]:
        now = time.monotonic() if now is None else now
        elapsed = max(0.0, now - self.updated_at)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.updated_at = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True, 0
        return False, max(1, math.ceil((1 - self.tokens) / self.refill_rate))


class RateLimiter:
    def __init__(self, default_limit: int, key_limits: dict[str, int] | None = None):
        self.default_limit = default_limit
        self.key_limits = key_limits or {}
        self._buckets: dict[str, TokenBucket] = {}

    def check(self, identity: str, *, api_key: str | None = None) -> tuple[bool, int]:
        bucket_key = f"api-key:{api_key}" if api_key and api_key in self.key_limits else f"ip:{identity}"
        limit = self.key_limits.get(api_key, self.default_limit)
        bucket = self._buckets.setdefault(bucket_key, TokenBucket.create(limit))
        return bucket.consume()
