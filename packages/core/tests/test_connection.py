from __future__ import annotations

import pytest
from agentic_odi_core.connection import MCPConnectionConfig


@pytest.fixture(autouse=True)
def _clear_connection_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("AGENTIC_ODI_MCP_TIMEOUT", "AGENTIC_ODI_MCP_KEEPALIVE"):
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_sensible() -> None:
    config = MCPConnectionConfig.from_env()

    assert config.timeout == 30.0
    assert config.keepalive_interval == 15.0


def test_timeout_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_TIMEOUT", "120")

    assert MCPConnectionConfig.from_env().timeout == 120.0


def test_keepalive_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_KEEPALIVE", "20")

    assert MCPConnectionConfig.from_env().keepalive_interval == 20.0


def test_invalid_timeout_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_TIMEOUT", "nonsense")

    assert MCPConnectionConfig.from_env().timeout == 30.0


def test_non_positive_timeout_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_TIMEOUT", "0")

    assert MCPConnectionConfig.from_env().timeout == 30.0


def test_zero_keepalive_disables_the_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_KEEPALIVE", "0")

    assert MCPConnectionConfig.from_env().keepalive_interval is None


def test_invalid_keepalive_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_KEEPALIVE", "soon")

    assert MCPConnectionConfig.from_env().keepalive_interval == 15.0
