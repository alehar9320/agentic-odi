"""The MCP server port must be overridable for dev and multi-instance runs."""

from __future__ import annotations

import pytest
from agentic_odi_mcp_server.mcp_server import DEFAULT_PORT, resolve_port


def test_default_port_is_8000(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTIC_ODI_MCP_PORT", raising=False)

    assert DEFAULT_PORT == 8000
    assert resolve_port() == 8000


def test_env_var_overrides_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_PORT", "9200")

    assert resolve_port() == 9200


def test_flag_wins_over_the_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_PORT", "9200")

    assert resolve_port(9300) == 9300


def test_blank_env_var_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_PORT", "  ")

    assert resolve_port() == DEFAULT_PORT


def test_a_non_numeric_env_var_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_PORT", "eight thousand")

    with pytest.raises(ValueError, match="AGENTIC_ODI_MCP_PORT must be an integer"):
        resolve_port()
