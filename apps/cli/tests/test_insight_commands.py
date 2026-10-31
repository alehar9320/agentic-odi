"""The insight commands work on the local backend, without an MCP server."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner


def test_evaluate_reports_a_well_formed_statement(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))

    result = CliRunner().invoke(
        app, ["evaluate", "Minimize the time to ship when onboarding a new customer"]
    )

    assert result.exit_code == 0
    assert "passes" in result.stdout


def test_evaluate_lists_what_needs_fixing(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))

    result = CliRunner().invoke(app, ["evaluate", "better"])

    assert result.exit_code == 0
    assert "needs work" in result.stdout
    assert "Minimize" in result.stdout


def test_evaluate_json_is_the_mcp_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))

    result = CliRunner().invoke(app, ["evaluate", "--json", "Minimize the time to ship when live"])

    assert result.exit_code == 0
    assert '"valid": true' in result.stdout


def test_capabilities_and_guidelines_print_core_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    runner = CliRunner()

    capabilities = runner.invoke(app, ["capabilities"])
    guidelines = runner.invoke(app, ["guidelines"])

    assert capabilities.exit_code == 0
    assert "Agentic ODI assistant" in capabilities.stdout
    assert guidelines.exit_code == 0
    assert "Outcome-Driven Innovation" in guidelines.stdout


def test_health_reports_an_accessible_store(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))

    result = CliRunner().invoke(app, ["health"])

    assert result.exit_code == 0
    assert "ok" in result.stdout
    assert "accessible" in result.stdout


def test_health_json_is_the_mcp_shape(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))

    result = CliRunner().invoke(app, ["health", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"status": "ok", "store": "accessible"}
