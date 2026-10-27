"""The CLI's local backend must stay aligned with the core contract."""

from __future__ import annotations

from agentic_odi_cli.backend import _LOCAL_HANDLERS
from agentic_odi_core.contract import TOOL_NAMES


def test_local_handler_keys_equal_contract_tool_names() -> None:
    assert set(_LOCAL_HANDLERS) == set(TOOL_NAMES)
