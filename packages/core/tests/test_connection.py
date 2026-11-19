"""MCP connection settings, read and validated in one place (issue #1084).

A malformed value names the variable and the form it accepts instead of
quietly becoming the default, which is what made ``AGENTIC_ODI_MCP_TIMEOUT=30s``
read as thirty seconds with nobody told.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.connection import MCPConnectionConfig
from agentic_odi_core.errors import ConfigurationError


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


def test_an_invalid_timeout_names_the_variable_and_the_accepted_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_TIMEOUT", "30s")

    with pytest.raises(ConfigurationError) as exc_info:
        MCPConnectionConfig.from_env()

    message = str(exc_info.value)
    assert "AGENTIC_ODI_MCP_TIMEOUT" in message
    assert "30s" in message


def test_a_non_positive_timeout_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_TIMEOUT", "0")

    with pytest.raises(ConfigurationError):
        MCPConnectionConfig.from_env()


def test_zero_keepalive_disables_the_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_KEEPALIVE", "0")

    assert MCPConnectionConfig.from_env().keepalive_interval is None


def test_a_negative_keepalive_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_KEEPALIVE", "-5")

    with pytest.raises(ConfigurationError):
        MCPConnectionConfig.from_env()


def test_an_empty_value_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MCP_TIMEOUT", "  ")

    assert MCPConnectionConfig.from_env().timeout == 30.0
