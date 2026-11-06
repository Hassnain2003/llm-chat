"""Async request queue with configurable depth."""

from __future__ import annotations

from gateway.metrics import queue_depth


class RequestQueue:
    def __init__(self, max_depth: int = 100):
        self._max = max_depth
        self._active = 0

    def try_acquire(self) -> bool:
        if self._active >= self._max:
            return False
        self._active += 1
        queue_depth.set(self._active)
        return True

    def release(self) -> None:
        self._active = max(0, self._active - 1)
        queue_depth.set(self._active)

    @property
    def depth(self) -> int:
        return self._active

    def is_full(self) -> bool:
        return self._active >= self._max
