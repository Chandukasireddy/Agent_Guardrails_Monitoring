"""A process-wide sliding-window limiter for paid or quota-limited APIs.

Every model call from this process (guard replies, tool rounds, LLM judges, CLI attacks)
goes through one limiter per API key, so 40 requests per minute is shared by all players.
Callers wait for a free slot for a short time; if none frees up they get an LLMError the
player can read, instead of the API returning 429 to the room.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable

from .base import LLMError


class SlidingWindowLimiter:
    def __init__(
        self,
        max_calls: int,
        window_seconds: float = 60.0,
        max_wait_seconds: float = 20.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be at least 1")
        self.max_calls = max_calls
        self.window = window_seconds
        self.max_wait = max_wait_seconds
        self._clock = clock
        self._sleep = sleep
        self._stamps: deque[float] = deque()
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        while self._stamps and now - self._stamps[0] >= self.window:
            self._stamps.popleft()

    def acquire(self) -> None:
        """Reserve one call. Waits up to ``max_wait`` seconds, then raises LLMError."""
        deadline = self._clock() + self.max_wait
        while True:
            with self._lock:
                now = self._clock()
                self._prune(now)
                if len(self._stamps) < self.max_calls:
                    self._stamps.append(now)
                    return
                free_in = self.window - (now - self._stamps[0])
            if now + free_in > deadline:
                raise LLMError(
                    f"The guard is busy (the API allows {self.max_calls} requests a minute). "
                    "Give it a few seconds and try again."
                )
            self._sleep(max(0.05, min(free_in, 1.0)))

    def in_window(self) -> int:
        with self._lock:
            self._prune(self._clock())
            return len(self._stamps)


_limiters: dict[str, SlidingWindowLimiter] = {}
_registry_lock = threading.Lock()


def limiter_for(key: str, max_calls: int) -> SlidingWindowLimiter:
    """One limiter per API key, shared by every provider object that uses that key."""
    with _registry_lock:
        if key not in _limiters:
            _limiters[key] = SlidingWindowLimiter(max_calls)
        return _limiters[key]
