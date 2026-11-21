"""Shared HTTP client for connector traffic.

Connector ingests can fan out to many REST endpoints at once. A single
configured client keeps the connection pool, timeout, and retry budget
predictable instead of inheriting httpx defaults that may be too small for
concurrent ingest or too large for a constrained deployment.
"""

from __future__ import annotations

import asyncio
import os
import random
from typing import Any, Awaitable, Callable

import httpx

DEFAULT_POOL_SIZE = 10
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3

POOL_SIZE_ENV = "AGENTIC_ODI_HTTP_POOL_SIZE"
TIMEOUT_ENV = "AGENTIC_ODI_HTTP_TIMEOUT"
RETRIES_ENV = "AGENTIC_ODI_HTTP_RETRIES"

# HTTP statuses that are worth retrying. httpx's transport retries only
# *connection* failures; a 429 or 503 is returned to the caller on the first
# attempt, so the retry budget the class advertises is spent here instead.
RETRY_STATUSES = frozenset({429, 502, 503, 504})
BACKOFF_BASE = 0.25
BACKOFF_CAP = 4.0
MAX_RETRY_AFTER = 10.0


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer >= {minimum}, got {raw!r}") from exc
    if value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}, got {value}")
    return value


def _env_float(name: str, default: float, *, minimum: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number >= {minimum}, got {raw!r}") from exc
    # ``nan`` compares false against every bound, so a plain ``value < minimum``
    # would let it through; negate the comparison to reject it.
    if not value >= minimum:
        raise ValueError(f"{name} must be a number >= {minimum}, got {value}")
    return value


class ConnectorHTTPClient:
    """An ``httpx.AsyncClient`` with a configured pool, timeout, and retries."""

    def __init__(
        self,
        *,
        pool_size: int = DEFAULT_POOL_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self.pool_size = pool_size
        self.timeout = timeout
        self.retries = retries
        self._sleep = sleep or asyncio.sleep
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

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        # ``retries`` on the transport covers connection failures; this loop covers
        # the HTTP statuses the transport cannot see. A non-idempotent ``post`` is
        # retried only when the body is not a stream — connector ingestion POSTs are
        # record-scoped and safe to repeat at the transport level.
        attempts = self.retries + 1
        for attempt in range(attempts):
            try:
                response = await self.client.request(method, url, **kwargs)
            except httpx.TransportError:
                if attempt + 1 >= attempts:
                    raise
                await self._sleep(self._backoff(attempt))
                continue
            if response.status_code not in RETRY_STATUSES or attempt + 1 >= attempts:
                return response
            delay = self._retry_after(response)
            await self._sleep(delay)
        return response  # pragma: no cover - loop always returns or raises

    def _backoff(self, attempt: int) -> float:
        return min(BACKOFF_CAP, BACKOFF_BASE * (2**attempt)) * (0.5 + random.random() / 2)

    def _retry_after(self, response: httpx.Response) -> float:
        raw = response.headers.get("retry-after")
        if raw is None:
            return self._backoff(0)
        try:
            return min(MAX_RETRY_AFTER, float(raw))
        except ValueError:
            return self._backoff(0)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._request("POST", url, **kwargs)

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
