"""Tests for the CLI's global backend context."""

from __future__ import annotations

from agentic_odi_cli import context


def test_set_options_is_returned_by_config() -> None:
    context.set_options(backend="mcp", db_path="odi.db", mcp_url="http://mcp")

    config = context.config()

    assert config.backend == "mcp"
    assert config.db_path == "odi.db"
    assert config.mcp_url == "http://mcp"


def test_selected_backend_prefers_the_option_then_the_environment(monkeypatch) -> None:
    context.set_options(backend="local")
    monkeypatch.setenv("AGENTIC_ODI_BACKEND", "mcp")
    assert context.selected_backend() == "local"

    context.set_options()
    assert context.selected_backend() == "mcp"

    monkeypatch.delenv("AGENTIC_ODI_BACKEND")
    assert context.selected_backend() == "local"
