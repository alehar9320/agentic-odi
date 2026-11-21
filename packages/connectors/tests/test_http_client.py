from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import httpx
import pytest
from agentic_odi_connectors import ConnectorHTTPClient, new_http_client


@pytest.fixture(autouse=True)
def _clear_http_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AGENTIC_ODI_HTTP_POOL_SIZE",
        "AGENTIC_ODI_HTTP_TIMEOUT",
        "AGENTIC_ODI_HTTP_RETRIES",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.asyncio
async def test_absent_values_use_defaults() -> None:
    async with new_http_client() as client:
        assert client.pool_size == 10
        assert client.timeout == 30.0
        assert client.retries == 3
        assert client.client.timeout.read == 30.0


@pytest.mark.asyncio
async def test_pool_size_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_HTTP_POOL_SIZE", "20")

    async with new_http_client() as client:
        assert client.pool_size == 20
        pool = cast(Any, client.client._transport)._pool
        assert pool._max_connections == 20


@pytest.mark.asyncio
async def test_timeout_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_HTTP_TIMEOUT", "60")

    async with new_http_client() as client:
        assert client.timeout == 60.0
        assert client.client.timeout.read == 60.0


@pytest.mark.asyncio
async def test_retries_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_HTTP_RETRIES", "0")

    async with new_http_client() as client:
        assert client.retries == 0


@pytest.mark.asyncio
async def test_invalid_environment_values_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_HTTP_POOL_SIZE", "not-a-number")
    monkeypatch.setenv("AGENTIC_ODI_HTTP_TIMEOUT", "-5")

    with pytest.raises(ValueError, match="AGENTIC_ODI_HTTP_POOL_SIZE"):
        new_http_client()


def test_a_typo_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_HTTP_POOL_SIZE", "not-a-number")

    with pytest.raises(ValueError, match="AGENTIC_ODI_HTTP_POOL_SIZE"):
        new_http_client()


def test_a_zero_timeout_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_HTTP_TIMEOUT", "0")

    with pytest.raises(ValueError, match="AGENTIC_ODI_HTTP_TIMEOUT"):
        new_http_client()


def test_a_nan_timeout_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_HTTP_TIMEOUT", "nan")

    with pytest.raises(ValueError, match="AGENTIC_ODI_HTTP_TIMEOUT"):
        new_http_client()


def test_a_negative_pool_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_HTTP_POOL_SIZE", "-1")

    with pytest.raises(ValueError, match="AGENTIC_ODI_HTTP_POOL_SIZE"):
        new_http_client()


@pytest.mark.asyncio
async def test_a_valid_value_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_HTTP_TIMEOUT", "2.5")

    async with new_http_client() as client:
        assert client.timeout == 2.5


@pytest.mark.asyncio
async def test_the_client_is_usable_as_an_async_context_manager() -> None:
    async with ConnectorHTTPClient(pool_size=4) as client:
        assert client.client.is_closed is False
    assert client.client.is_closed is True


# --- status-aware retries -------------------------------------------------
#
# ``httpx.AsyncHTTPTransport(retries=...)`` only retries connection failures, so
# a 429 with ``Retry-After`` or a 502/503/504 used to reach the caller on the
# first attempt. These tests pin the loop that now sits on top of the transport:
# which statuses are retried, that ``Retry-After`` is honoured, that the attempt
# count is bounded, and that a persistent transport error still propagates.

Handler = Callable[[httpx.Request], httpx.Response]


class SleepRecorder:
    """A ``sleep`` seam that records delays instead of waiting on a clock."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def _counting_handler(
    responses: list[httpx.Response | Exception],
) -> tuple[Handler, dict[str, int]]:
    """Return a handler that replays ``responses`` and counts the calls made."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        index = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        item = responses[index]
        if isinstance(item, Exception):
            raise item
        return item

    return handler, calls


def _make_client(
    handler: Handler, *, retries: int = 3
) -> tuple[ConnectorHTTPClient, SleepRecorder]:
    sleeps = SleepRecorder()
    client = ConnectorHTTPClient(retries=retries, sleep=sleeps)
    # Swap in a mock transport so the loop is exercised without a network.
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client, sleeps


@pytest.mark.asyncio
async def test_a_429_with_retry_after_is_retried() -> None:
    handler, calls = _counting_handler(
        [httpx.Response(429, headers={"Retry-After": "0"}), httpx.Response(200, text="ok")]
    )
    client, sleeps = _make_client(handler, retries=3)
    try:
        response = await client.get("http://test/ingest")
    finally:
        await client.aclose()

    assert response.status_code == 200
    assert calls["n"] == 2
    # The wait came from the upstream's own header, not the backoff ladder.
    assert sleeps.delays == [0.0]


@pytest.mark.asyncio
async def test_a_500_is_not_retried() -> None:
    handler, calls = _counting_handler([httpx.Response(500)])
    client, sleeps = _make_client(handler, retries=3)
    try:
        response = await client.post("http://test/hook", json={"a": 1})
    finally:
        await client.aclose()

    assert response.status_code == 500
    assert calls["n"] == 1
    assert sleeps.delays == []


@pytest.mark.asyncio
async def test_attempts_are_bounded() -> None:
    handler, calls = _counting_handler([httpx.Response(503)])
    client, sleeps = _make_client(handler, retries=3)
    try:
        response = await client.get("http://test/ingest")
    finally:
        await client.aclose()

    # Exactly ``retries + 1`` requests, and the last response is returned
    # rather than raising, so callers keep handling non-2xx themselves.
    assert calls["n"] == 4
    assert response.status_code == 503
    assert len(sleeps.delays) == 3


@pytest.mark.asyncio
async def test_a_transport_error_before_the_budget_is_spent_raises() -> None:
    handler, calls = _counting_handler([httpx.ConnectError("boom")])
    client, sleeps = _make_client(handler, retries=2)
    try:
        with pytest.raises(httpx.TransportError):
            await client.get("http://test/ingest")
    finally:
        await client.aclose()

    assert calls["n"] == 3
    assert len(sleeps.delays) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 502, 503, 504])
async def test_transient_statuses_are_retried(status: int) -> None:
    handler, calls = _counting_handler([httpx.Response(status), httpx.Response(200)])
    client, _ = _make_client(handler, retries=2)
    try:
        response = await client.get("http://test/ingest")
    finally:
        await client.aclose()

    assert calls["n"] == 2
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 404, 500])
async def test_non_transient_statuses_are_not_retried(status: int) -> None:
    handler, calls = _counting_handler([httpx.Response(status)])
    client, _ = _make_client(handler, retries=2)
    try:
        response = await client.get("http://test/ingest")
    finally:
        await client.aclose()

    assert calls["n"] == 1
    assert response.status_code == status


@pytest.mark.asyncio
async def test_retry_after_is_clamped_to_the_ceiling() -> None:
    handler, calls = _counting_handler(
        [httpx.Response(429, headers={"Retry-After": "600"}), httpx.Response(200)]
    )
    client, sleeps = _make_client(handler, retries=3)
    try:
        response = await client.get("http://test/ingest")
    finally:
        await client.aclose()

    assert response.status_code == 200
    assert calls["n"] == 2
    assert sleeps.delays and sleeps.delays[0] <= 10.0
