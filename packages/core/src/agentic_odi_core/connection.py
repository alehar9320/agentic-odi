"""MCP connection settings shared by the CLI and Studio.

The parsing lives in :mod:`agentic_odi_core.settings`; this module keeps the
public name the rest of the workspace imports. ``MCPConnectionConfig`` is an
alias for :class:`~agentic_odi_core.settings.MCPConnectionSettings` for one
release so no import breaks, and ``from_env()`` stays the only entry point.
"""

from __future__ import annotations

from agentic_odi_core.settings import (
    DEFAULT_MCP_KEEPALIVE,
    DEFAULT_MCP_TIMEOUT,
    KEEPALIVE_ENV,
    TIMEOUT_ENV,
    MCPConnectionSettings,
)

MCPConnectionConfig = MCPConnectionSettings

__all__ = [
    "DEFAULT_MCP_KEEPALIVE",
    "DEFAULT_MCP_TIMEOUT",
    "KEEPALIVE_ENV",
    "MCPConnectionConfig",
    "MCPConnectionSettings",
    "TIMEOUT_ENV",
]
