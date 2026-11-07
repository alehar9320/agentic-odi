import pytest
from agentic_odi_connectors.models import RateLimitExceededError
from agentic_odi_connectors.rate_limit import (
    DEFAULT_INGEST_RATE,
    INGEST_RATE_ENV,
    RateLimiter,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_default_rate_is_hundred_per_second(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(INGEST_RATE_ENV, raising=False)

    limiter = RateLimiter.from_env()

    assert DEFAULT_INGEST_RATE == 100
    assert limiter.rate == 100
    assert limiter.burst == 100


def test_rate_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(INGEST_RATE_ENV, "25")

    limiter = RateLimiter.from_env()

    assert limiter.rate == 25
    assert limiter.burst == 25


@pytest.mark.parametrize("raw", ["", "fast", "0", "-5"])
def test_invalid_rate_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv(INGEST_RATE_ENV, raw)

    assert RateLimiter.from_env().rate == DEFAULT_INGEST_RATE


def test_acquire_allows_a_burst_up_to_the_bucket() -> None:
    clock = FakeClock()
    limiter = RateLimiter(rate=2, burst=3, clock=clock)

    limiter.acquire(3)

    with pytest.raises(RateLimitExceededError):
        limiter.acquire(1)


def test_tokens_refill_with_time() -> None:
    clock = FakeClock()
    limiter = RateLimiter(rate=2, burst=2, clock=clock)
    limiter.acquire(2)

    clock.advance(0.5)
    limiter.acquire(1)

    with pytest.raises(RateLimitExceededError):
        limiter.acquire(1)


def test_bucket_caps_refill_at_its_burst() -> None:
    clock = FakeClock()
    limiter = RateLimiter(rate=10, burst=2, clock=clock)

    clock.advance(60)
    limiter.acquire(2)

    with pytest.raises(RateLimitExceededError):
        limiter.acquire(1)


def test_reset_refills_the_bucket() -> None:
    clock = FakeClock()
    limiter = RateLimiter(rate=1, burst=1, clock=clock)
    limiter.acquire(1)

    limiter.reset()

    limiter.acquire(1)


def test_a_request_larger_than_the_burst_is_refused() -> None:
    limiter = RateLimiter(rate=1, burst=1, clock=FakeClock())

    with pytest.raises(RateLimitExceededError) as excinfo:
        limiter.acquire(2)

    assert excinfo.value.rate == 1
    assert excinfo.value.requested == 2


def test_acquire_rejects_a_non_positive_request() -> None:
    limiter = RateLimiter(rate=1, burst=1, clock=FakeClock())

    with pytest.raises(ValueError):
        limiter.acquire(0)
