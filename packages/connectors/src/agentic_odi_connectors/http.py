"""Shared HTTP client for connector traffic.

Connector ingests can fan out to many REST endpoints at once. A single
configured client keeps the connection pool, timeout, and retry budget
predictable instead of inheriting httpx defaults that may be too small for
concurrent ingest or too large for a constrained deployment.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_POOL_SIZE = 10
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3

POOL_SIZE_ENV = "AGENTIC_ODI_HTTP_POOL_SIZE"
TIMEOUT_ENV = "AGENTIC_ODI_HTTP_TIMEOUT"
RETRIES_ENV = "AGENTIC_ODI_HTTP_RETRIES"


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


def _env_float(name: str, default: float, *, minimum: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


class ConnectorHTTPClient:
    """An ``httpx.AsyncClient`` with a configured pool, timeout, and retries."""

    def __init__(
        self,
        *,
        pool_size: int = DEFAULT_POOL_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        self.pool_size = pool_size
        self.timeout = timeout
        self.retries = retries
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            transport=httpx.AsyncHTTPTransport(
                retries=retries,
                limits=httpx.Limits(
                    max_connections=pool_size,
                    max_keepalive_connections=pool_size,
                ),
            ),
        )

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.client.get(url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.client.post(url, **kwargs)

    async def aclose(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> ConnectorHTTPClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


def get_http_client() -> ConnectorHTTPClient:
    """Build a client from the connector HTTP environment variables."""
    return ConnectorHTTPClient(
        pool_size=_env_int(POOL_SIZE_ENV, DEFAULT_POOL_SIZE, minimum=1),
        timeout=_env_float(TIMEOUT_ENV, DEFAULT_TIMEOUT, minimum=0.001),
        retries=_env_int(RETRIES_ENV, DEFAULT_RETRIES, minimum=0),
    )
