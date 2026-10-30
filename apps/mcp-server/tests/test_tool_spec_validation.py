"""Startup validation refuses a contract that the server cannot serve."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest
from agentic_odi_core.contract import TOOL_SPECS
from agentic_odi_mcp_server import mcp_server


def _live_tools():
    return asyncio.run(mcp_server.mcp.list_tools())


def test_live_registry_matches_the_contract():
    assert mcp_server.validate_tool_specs(tools=_live_tools()) == []


def test_a_missing_handler_is_reported():
    tools = [tool for tool in _live_tools() if tool.name != "add_job"]

    errors = mcp_server.validate_tool_specs(tools=tools)

    assert any("add_job" in error and "handler" in error for error in errors)


def test_an_argument_mismatch_is_reported():
    specs = dict(TOOL_SPECS)
    specs["add_job"] = replace(TOOL_SPECS["add_job"], arguments=("name",), required=("name",))

    errors = mcp_server.validate_tool_specs(specs=specs, tools=_live_tools())

    assert any("add_job" in error and "arguments" in error for error in errors)


def test_a_missing_enum_spec_is_reported():
    specs = {name: spec for name, spec in TOOL_SPECS.items() if name != "add_job"}

    errors = mcp_server.validate_tool_specs(specs=specs, tools=[])

    assert any("add_job" in error and "ToolName" in error for error in errors)


def test_a_duplicate_handler_is_reported():
    tools = _live_tools()

    errors = mcp_server.validate_tool_specs(tools=[*tools, tools[0]])

    assert any("duplicate" in error.lower() for error in errors)


def test_startup_exits_when_validation_fails(monkeypatch, capsys):
    monkeypatch.setattr(mcp_server, "validate_tool_specs", lambda **_: ["add_job: broken"])

    with pytest.raises(SystemExit) as exc:
        mcp_server.validate_at_startup()

    assert exc.value.code == 1
    assert "add_job: broken" in capsys.readouterr().err


def test_startup_is_silent_when_valid(monkeypatch, capsys):
    monkeypatch.setattr(mcp_server, "validate_tool_specs", lambda **_: [])

    mcp_server.validate_at_startup()

    assert capsys.readouterr().err == ""


def test_main_validates_before_serving(monkeypatch):
    calls: list[object] = []
    monkeypatch.setattr(mcp_server, "validate_at_startup", lambda: calls.append("validate"))
    monkeypatch.setattr(mcp_server.mcp, "run", lambda **kwargs: calls.append("run"))

    mcp_server.main([])

    assert calls == ["validate", "run"]
