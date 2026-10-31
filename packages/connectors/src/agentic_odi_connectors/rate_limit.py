"""Token-bucket rate limiting for the connector ingest sink."""

from __future__ import annotations

import os
import time
from collections.abc import Callable

from agentic_odi_connectors.models import RateLimitExceededError

DEFAULT_INGEST_RATE = 100
INGEST_RATE_ENV = "AGENTIC_ODI_INGEST_RATE"


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


class RateLimiter:
    """A token bucket that admits records up to ``rate`` per second.

    ``burst`` caps how many tokens the bucket may hold; the default is one
    second's worth. ``acquire`` never blocks: when the bucket is empty it
    raises :class:`RateLimitExceededError`, so a burst is shed rather than
    queued in memory.
    """

    def __init__(
        self,
        rate: float = DEFAULT_INGEST_RATE,
        burst: int | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        self.rate = rate
        self.burst = burst if burst is not None else max(1, int(rate))
        if self.burst < 1:
            raise ValueError("burst must be at least 1")
        self._clock = clock
        self._tokens = float(self.burst)
        self._updated = clock()

    @classmethod
    def from_env(cls) -> RateLimiter:
        """Build a limiter from ``AGENTIC_ODI_INGEST_RATE`` (records/second)."""
        return cls(rate=_positive_int(INGEST_RATE_ENV, DEFAULT_INGEST_RATE))

    def acquire(self, tokens: int = 1) -> None:
        """Admit ``tokens`` records or raise if the bucket cannot hold them."""
        if tokens < 1:
            raise ValueError("tokens must be at least 1")
        now = self._clock()
        self._tokens = min(self.burst, self._tokens + (now - self._updated) * self.rate)
        self._updated = now
        if tokens > self.burst or self._tokens < tokens:
            raise RateLimitExceededError(rate=self.rate, requested=tokens)
        self._tokens -= tokens

    def reset(self) -> None:
        """Refill the bucket to its burst."""
        self._tokens = float(self.burst)
        self._updated = self._clock()
