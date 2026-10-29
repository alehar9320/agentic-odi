"""The CLI's local backend must stay aligned with the core contract.

Every tool in :data:`TOOL_NAMES` must have a local handler so that
``--backend local`` can reach every tool the MCP server exposes.
"""

from __future__ import annotations

from agentic_odi_cli.backend import _LOCAL_HANDLERS
from agentic_odi_core.contract import TOOL_NAMES


def test_local_handler_keys_equal_contract_tools() -> None:
    """The local handler set must equal TOOL_NAMES (not a subset).

    This is the single most valuable line in issue #84: it converts a
    documented drift allowance into a hard invariant. Every new tool must
    be reachable from the terminal.
    """
    assert set(_LOCAL_HANDLERS) == set(TOOL_NAMES)
