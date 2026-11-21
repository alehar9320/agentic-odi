"""The HTTP client factory owns nothing; its callers own the client.

``new_http_client()`` builds a fresh client with its own connection pool on
every call, so a caller that wants one pool per ingest run must keep one client
and close it. These tests pin that contract: distinct calls yield distinct
clients, and the async context manager closes the pool on the way out.
"""

from __future__ import annotations

import pytest
from agentic_odi_connectors import new_http_client


@pytest.fixture(autouse=True)
def _clear_http_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AGENTIC_ODI_HTTP_POOL_SIZE",
        "AGENTIC_ODI_HTTP_TIMEOUT",
        "AGENTIC_ODI_HTTP_RETRIES",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.asyncio
async def test_each_call_returns_a_distinct_client() -> None:
    first = new_http_client()
    second = new_http_client()
    try:
        assert first is not second
        assert first.client is not second.client
    finally:
        await first.aclose()
        await second.aclose()


@pytest.mark.asyncio
async def test_the_context_manager_closes_it() -> None:
    async with new_http_client() as client:
        assert client.client.is_closed is False
    assert client.client.is_closed is True
