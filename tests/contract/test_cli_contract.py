"""The CLI's local backend must stay aligned with the core contract.

The local handler surface mirrors the live MCP tool surface exactly: every
contract tool has a local handler, and no local handler exists without a
contract tool. This keeps the local (SQLite) and remote (MCP) backends in
lockstep.
"""

from __future__ import annotations

from agentic_odi_cli.backend import _LOCAL_HANDLERS
from agentic_odi_core.contract import TOOL_NAMES


def test_local_handlers_match_mcp_tool_names() -> None:
    """CLI local handlers are in one-to-one parity with MCP tool names."""
    assert set(_LOCAL_HANDLERS) == set(TOOL_NAMES)


def test_every_local_handler_is_a_contract_tool() -> None:
    assert set(_LOCAL_HANDLERS) <= set(TOOL_NAMES)
