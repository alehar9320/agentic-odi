"""Connection probing and LLM health checks, ported from the Streamlit app."""

from __future__ import annotations

import asyncio
import os
import socket
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, NamedTuple
from urllib.parse import urlparse

from openai import AsyncOpenAI

DEFAULT_BASE_URL = "http://localhost:8001/v1"
DEFAULT_API_KEY = "local"
DEFAULT_MODEL = "local-tools-model"
DEFAULT_MCP_URL = "http://localhost:8000/mcp"

OFFLINE_MESSAGE = "LLM server offline (Local Studio Mode enabled)"

#: How long a probe result may be reused before it is considered stale.
_PROBE_TTL_SECONDS = 30.0

#: Ceiling on cached entries so opening many tabs / endpoints cannot grow the
#: map without bound. Stale entries are evicted on read; the map is trimmed to
#: this cap on write.
_PROBE_CACHE_CAP = 512


class ProbeResult(NamedTuple):
    """The outcome of one probe, stamped when it was obtained.

    Only the boolean and the reason message a probe already returns are kept --
    never a credential or a response body.
    """

    healthy: bool
    message: str
    checked_at: str  # ISO 8601 UTC


#: (endpoint, model) -> (monotonic timestamp, ProbeResult). Keyed on the
#: endpoint and model only -- never on a credential -- so concurrent tabs
#: sharing an endpoint reuse a single probe.
_PROBE_CACHE: OrderedDict[tuple[str, str], tuple[float, ProbeResult]] = OrderedDict()
_PROBE_CACHE_LOCK = threading.Lock()


def _iso_utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _evict_stale(now: float) -> None:
    """Drop cache entries older than the TTL."""
    stale = [key for key, (ts, _) in _PROBE_CACHE.items() if now - ts > _PROBE_TTL_SECONDS]
    for key in stale:
        _PROBE_CACHE.pop(key, None)


def _trim_to_cap() -> None:
    """Drop the oldest entries until the cache is within its cap."""
    while len(_PROBE_CACHE) > _PROBE_CACHE_CAP:
        _PROBE_CACHE.popitem(last=False)


def _load_profile_fallback() -> dict[str, str]:
    """Read llm_profile.json directly without importing cli package."""
    import json
    from pathlib import Path

    xdg = os.getenv("XDG_CONFIG_HOME")
    cfg_dir = Path(xdg) / "agentic-odi" if xdg else Path.home() / ".config" / "agentic-odi"
    profile_file = cfg_dir / "llm_profile.json"
    if not profile_file.exists():
        return {}
    try:
        with open(profile_file) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def defaults() -> dict[str, str]:
    """Streamlit-compatible environment defaults (same variable names).

    Priority order: environment variable > persisted llm_profile.json > hardcoded constant.
    """
    profile = _load_profile_fallback()
    return {
        "base_url": os.getenv("AGENTIC_ODI_BASE_URL")
        or profile.get("base_url")
        or DEFAULT_BASE_URL,
        "api_key": os.getenv("AGENTIC_ODI_API_KEY") or profile.get("api_key") or DEFAULT_API_KEY,
        "model_name": os.getenv("AGENTIC_ODI_MODEL") or profile.get("model") or DEFAULT_MODEL,
        "mcp_url": os.getenv("AGENTIC_ODI_MCP_URL") or profile.get("mcp_url") or DEFAULT_MCP_URL,
    }


def is_endpoint_reachable(url: str, timeout: float = 0.3) -> bool:
    """Quick socket check to verify a port is open without hanging on HTTP reads."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def classify_llm_error(exc: Exception) -> tuple[str, str]:
    message = str(exc)
    lower = message.lower()
    connection_indicators = [
        "connection error",
        "connection aborted",
        "failed to establish a new connection",
        "timed out",
        "timeout",
        "connection refused",
    ]
    if any(indicator in lower for indicator in connection_indicators):
        return "connection_error", message
    return "error", message


async def list_models(base_url: str, api_key: str) -> tuple[list[str], str | None]:
    """Model ids the configured backend reports, and why that list is empty.

    The browser cannot ask the backend itself — the model server is not
    necessarily CORS-open, and its address may only be reachable from here —
    so the sidecar asks on the user's behalf and never raises: a failed probe
    is a message the picker can show, not a 500.
    """
    if not is_endpoint_reachable(base_url, timeout=0.4):
        return [], OFFLINE_MESSAGE

    client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=2.0)
    try:
        page = await asyncio.wait_for(client.models.list(), timeout=2.0)
    except Exception as exc:  # noqa: BLE001
        status, detail = classify_llm_error(exc)
        return [], f"{status}: {detail}"

    # The async SDK returns an `AsyncPage`, whose items live on `.data`; the page
    # itself is not synchronously iterable, so read the payload explicitly. A
    # compatible server with an unusual shape yields no ids rather than a 500.
    items = getattr(page, "data", None) or []
    ids = {str(getattr(model, "id", "") or "") for model in items}
    return sorted(model_id for model_id in ids if model_id), None


async def _probe_llm_health(base_url: str, api_key: str, model_name: str) -> tuple[bool, str]:
    """The actual network probe: socket pre-check, then model list."""

    if not is_endpoint_reachable(base_url, timeout=0.3):
        return False, OFFLINE_MESSAGE

    client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=1.2)
    try:
        await asyncio.wait_for(client.models.list(), timeout=1.2)
        return True, "LLM backend is reachable."
    except Exception as exc:  # noqa: BLE001
        status, detail = classify_llm_error(exc)
        return False, f"{status}: {detail}"


async def check_llm_health(base_url: str, api_key: str, model_name: str) -> tuple[bool, str]:
    """Non-blocking LLM health probe with an instant socket pre-check.

    Pure probe with no caching: every call re-checks the endpoint. Chat and
    other callers that must see fresh results use this directly; the HTTP route
    uses :func:`probe_llm_health` when it wants a TTL cache.
    """

    return await _probe_llm_health(base_url, api_key, model_name)


async def probe_llm_health(
    base_url: str,
    api_key: str,
    model_name: str,
    now: Callable[[], float] = time.monotonic,
    fresh: bool = False,
) -> dict[str, Any]:
    """Probe with a TTL cache so concurrent tabs cause one upstream probe.

    Returns ``{"healthy", "message", "checked_at", "cached"}``. When ``fresh``
    is true the cache is bypassed and the entry refreshed, so a user-initiated
    "check now" is never stale. Results are keyed on (endpoint, model) -- never
    on a credential -- and the map is bounded by TTL eviction and a size cap.
    """

    key = (base_url, model_name)
    t = now()

    with _PROBE_CACHE_LOCK:
        _evict_stale(t)
        if not fresh:
            entry = _PROBE_CACHE.get(key)
            if entry is not None:
                stored_ts, stored = entry
                if t - stored_ts <= _PROBE_TTL_SECONDS:
                    return {
                        "healthy": stored.healthy,
                        "message": stored.message,
                        "checked_at": stored.checked_at,
                        "cached": True,
                    }

    healthy, message = await _probe_llm_health(base_url, api_key, model_name)
    result = ProbeResult(healthy=healthy, message=message, checked_at=_iso_utc(t))

    with _PROBE_CACHE_LOCK:
        _PROBE_CACHE[key] = (t, result)
        _trim_to_cap()

    return {
        "healthy": result.healthy,
        "message": result.message,
        "checked_at": result.checked_at,
        "cached": False,
    }
