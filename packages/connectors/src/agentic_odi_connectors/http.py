"""Shared HTTP client for connector traffic.

Connector ingests can fan out to many REST endpoints at once, so the client
carries a configured connection pool, timeout, and retry budget instead of
inheriting httpx defaults that may be too small for concurrent ingest or too
large for a constrained deployment.

The retry budget is split on purpose. ``httpx.AsyncHTTPTransport(retries=...)``
retries *connection* failures below the client, while :meth:`_request` retries
*HTTP statuses* (429/502/503/504) on top of it. Remove neither half: a connect
failure is cleared by the transport, a rate-limit or bad-gateway status by the
loop.

``new_http_client()`` is a factory, not a singleton: every call builds a new
client, and the caller owns its lifetime. Use it as an async context manager
so the pool is closed when the ingest run ends::

    async with new_http_client() as client:
        ...

A client left unclosed leaks its connection pool, so a loop that calls the
factory per record without closing opens one pool per record. There is no
process-wide client and nothing closes a client the caller forgot.
"""

from __future__ import annotations

import asyncio
import os
import random
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

DEFAULT_POOL_SIZE = 10
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3

# Statuses worth another attempt: the upstream is momentarily unavailable, not
# answering "no". Everything else (a 400/401/404/500) is a real answer.
RETRY_STATUSES = frozenset({429, 502, 503, 504})
BACKOFF_BASE = 0.25
BACKOFF_CAP = 4.0
# A server may ask for a long pause in ``Retry-After``; never wait longer than
# this before trying again.
MAX_RETRY_AFTER = 10.0

POOL_SIZE_ENV = "AGENTIC_ODI_HTTP_POOL_SIZE"
TIMEOUT_ENV = "AGENTIC_ODI_HTTP_TIMEOUT"
RETRIES_ENV = "AGENTIC_ODI_HTTP_RETRIES"


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
    """An ``httpx.AsyncClient`` with a configured pool, timeout, and retries.

    The instance owns the underlying client: close it with ``aclose()``, or
    enter it with ``async with`` so ``__aexit__`` closes it for you.
    """

    def __init__(
        self,
        *,
        pool_size: int = DEFAULT_POOL_SIZE,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.pool_size = pool_size
        self.timeout = timeout
        self.retries = retries
        self._sleep = sleep
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

    def _backoff(self, attempt: int) -> float:
        """A capped exponential delay with jitter, so retries do not sync up."""
        ceiling = min(BACKOFF_CAP, BACKOFF_BASE * 2**attempt)
        return ceiling * (0.5 + random.random() / 2)  # nosec B311 - backoff jitter, not a secret

    def _retry_delay(self, attempt: int, response: httpx.Response) -> float:
        """Honour a numeric ``Retry-After``, else fall back to the backoff ladder."""
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return min(MAX_RETRY_AFTER, float(retry_after))
            except ValueError:
                # ``Retry-After`` can be an HTTP-date; that is not a delay we
                # can sleep, so use the backoff ladder instead.
                pass
        return self._backoff(attempt)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(self.retries + 1):
            try:
                response = await self.client.request(method, url, **kwargs)
            except httpx.TransportError:
                # A connection-level failure the transport could not clear. Back
                # off and retry while the budget lasts, then let it propagate.
                if attempt >= self.retries:
                    raise
                await self._sleep(self._backoff(attempt))
                continue
            if response.status_code in RETRY_STATUSES and attempt < self.retries:
                await self._sleep(self._retry_delay(attempt, response))
                continue
            # A retryable status on the last attempt is returned, not raised:
            # callers already handle non-2xx, so raising would change behaviour
            # at every call site.
            return response
        # The loop always returns or raises; this is unreachable.
        raise RuntimeError("retry loop exhausted without a response")

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        # Connector ingestion POSTs are record-scoped, so repeating one at the
        # transport level is safe; this is why POST shares the GET retry loop.
        return await self._request("POST", url, **kwargs)

    async def aclose(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> ConnectorHTTPClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


def new_http_client() -> ConnectorHTTPClient:
    """Build a new client from the connector HTTP environment variables.

    This is a factory: each call returns a distinct client with its own
    connection pool. The caller owns it and must close it — prefer
    ``async with new_http_client() as client:`` so the pool is released.
    """
    return ConnectorHTTPClient(
        pool_size=_env_int(POOL_SIZE_ENV, DEFAULT_POOL_SIZE, minimum=1),
        timeout=_env_float(TIMEOUT_ENV, DEFAULT_TIMEOUT, minimum=0.001),
        retries=_env_int(RETRIES_ENV, DEFAULT_RETRIES, minimum=0),
    )
