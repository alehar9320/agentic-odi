"""MCP connection settings shared by the CLI and Studio."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_MCP_TIMEOUT = 30.0
DEFAULT_MCP_KEEPALIVE = 15.0

TIMEOUT_ENV = "AGENTIC_ODI_MCP_TIMEOUT"
KEEPALIVE_ENV = "AGENTIC_ODI_MCP_KEEPALIVE"


@dataclass(frozen=True)
class MCPConnectionConfig:
    """How long an MCP client waits, and how often it keeps a session alive.

    ``keepalive_interval`` is ``None`` when keepalive is disabled.
    """

    timeout: float = DEFAULT_MCP_TIMEOUT
    keepalive_interval: float | None = DEFAULT_MCP_KEEPALIVE

    @classmethod
    def from_env(cls) -> MCPConnectionConfig:
        return cls(
            timeout=_positive_float(TIMEOUT_ENV, DEFAULT_MCP_TIMEOUT),
            keepalive_interval=_keepalive_interval(),
        )


def _positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _keepalive_interval() -> float | None:
    raw = os.environ.get(KEEPALIVE_ENV)
    if not raw:
        return DEFAULT_MCP_KEEPALIVE
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_MCP_KEEPALIVE
    if value < 0:
        return DEFAULT_MCP_KEEPALIVE
    return value or None
