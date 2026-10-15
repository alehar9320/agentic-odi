"""Tests for Customer Outcomes CLI."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from cli.cli import app


def _strip_ansi(text: str) -> str:
    import re

    return re.compile(r"\x1b\[[0-9;]*m").sub("", text)


def test_outcomes_help_shows_subcommands():
    runner = CliRunner()
    result = runner.invoke(app, ["outcomes", "--help"])
    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    assert "outcomes" in output.lower() or "outcomes" in output


def test_outcomes_add_calls_mcp():
    runner = CliRunner()
    with patch("cli.outcomes._call_mcp") as mock_call:
        mock_call.return_value = "Customer outcome created successfully: {}"
        result = runner.invoke(
            app,
            [
                "--backend",
                "mcp",
                "outcomes",
                "add",
                "--job-id",
                "job-1",
                "--direction",
                "minimize",
                "--unit",
                "time",
                "--object",
                "to setup",
                "--statement",
                "Minimize time to setup",
                "--importance",
                "8.5",
                "--satisfaction",
                "4.0",
                "--category",
                "cost_reduction",
                "--business-statement",
                "Saves hours",
            ],
        )
    assert result.exit_code == 0
    mock_call.assert_called_once()


def test_score_calls_mcp():
    runner = CliRunner()
    with patch("cli.outcomes._call_mcp") as mock_call:
        mock_call.return_value = "Opportunity Score = 14.00"
        result = runner.invoke(app, ["--backend", "mcp", "outcomes", "score", "8", "2"])
    assert result.exit_code == 0
    mock_call.assert_called_once()


def test_outcomes_list_calls_mcp_with_args():
    from unittest.mock import patch

    from typer.testing import CliRunner

    from cli.cli import app

    runner = CliRunner()
    with patch("cli.outcomes._call_mcp") as mock_call:
        mock_call.return_value = "[]"
        runner.invoke(app, ["--backend", "mcp", "outcomes", "list", "--job-id", "job-1"])
    mock_call.assert_called_once()
