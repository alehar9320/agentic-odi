"""Connection probing and LLM health checks, ported from the Streamlit app."""

from __future__ import annotations

import asyncio
import os
import socket
from urllib.parse import urlparse

from openai import AsyncOpenAI

DEFAULT_BASE_URL = "http://localhost:8001/v1"
DEFAULT_API_KEY = "local"
DEFAULT_MODEL = "local-tools-model"
DEFAULT_MCP_URL = "http://localhost:8000/mcp"

OFFLINE_MESSAGE = "LLM server offline (Local Studio Mode enabled)"


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


async def check_llm_health(base_url: str, api_key: str, model_name: str) -> tuple[bool, str]:
    """Non-blocking LLM health probe with an instant socket pre-check."""
    if not is_endpoint_reachable(base_url, timeout=0.3):
        return False, OFFLINE_MESSAGE

    client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=1.2)
    try:
        await asyncio.wait_for(client.models.list(), timeout=1.2)
        return True, "LLM backend is reachable."
    except Exception as exc:  # noqa: BLE001
        status, detail = classify_llm_error(exc)
        return False, f"{status}: {detail}"
