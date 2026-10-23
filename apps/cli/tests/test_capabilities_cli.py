"""Tests for agentic-odi capabilities CLI commands."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_capabilities_summary_output() -> None:
    result = runner.invoke(app, ["capabilities"])
    assert result.exit_code == 0
    assert "Here is what I can help you with" in result.output
    assert "add_job" in result.output
    assert "get_capabilities" in result.output


def test_capabilities_json_manifest_output() -> None:
    result = runner.invoke(app, ["capabilities", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "tools" in data
    assert "add_job" in data["tools"]
    assert "evaluate_outcome" in data["tools"]


def test_capabilities_tools_command() -> None:
    result = runner.invoke(app, ["capabilities", "tools"])
    assert result.exit_code == 0
    assert "add_job" in result.output
    assert "get_capabilities_manifest" in result.output

    result_json = runner.invoke(app, ["capabilities", "tools", "--json"])
    assert result_json.exit_code == 0
    names = json.loads(result_json.output)
    assert "add_job" in names
    assert "evaluate_outcome" in names
