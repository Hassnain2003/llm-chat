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
    def __init__(
        self,
        default_limit: int,
        key_limits: dict[str, int] | None = None,
        *,
        bucket_ttl: float = 600,
        max_buckets: int = 10_000,
        clock=time.monotonic,
    ):
        self.default_limit = default_limit
        self.key_limits = key_limits or {}
        self.bucket_ttl = bucket_ttl
        self.max_buckets = max_buckets
        self._clock = clock
        self._buckets: dict[str, TokenBucket] = {}

    def check(self, identity: str, *, api_key: str | None = None) -> tuple[bool, int]:
        now = self._clock()
        self._evict(now)
        bucket_key = f"api-key:{api_key}" if api_key and api_key in self.key_limits else f"ip:{identity}"
        limit = self.key_limits.get(api_key, self.default_limit)
        bucket = self._buckets.get(bucket_key)
        if bucket is None:
            self._evict_to_capacity(now)
            bucket = TokenBucket.create(limit)
            self._buckets[bucket_key] = bucket
        allowed, retry_after = bucket.consume(now)
        return allowed, retry_after

    def _evict(self, now: float) -> None:
        idle_keys = [
            key for key, bucket in self._buckets.items()
            if now - bucket.updated_at >= self.bucket_ttl
        ]
        for key in idle_keys:
            del self._buckets[key]

    def _evict_to_capacity(self, now: float) -> None:
        while len(self._buckets) >= self.max_buckets:
            oldest_key = min(self._buckets, key=lambda key: self._buckets[key].updated_at)
            del self._buckets[oldest_key]
