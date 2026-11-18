from __future__ import annotations

from typing import Any, cast

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
        get_http_client()


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
        get_http_client()


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
