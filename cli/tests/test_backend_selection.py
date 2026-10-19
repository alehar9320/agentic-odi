from unittest.mock import patch

from typer.testing import CliRunner

from cli.cli import app

ADD_ARGS = [
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
    "Minimize time",
    "--importance",
    "8.5",
    "--satisfaction",
    "4.0",
    "--category",
    "cost_reduction",
    "--business-statement",
    "Saves hours",
]


def test_outcomes_add_defaults_to_local(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    runner = CliRunner()
    with patch("cli.backend._call_mcp") as mock_call:
        result = runner.invoke(app, ADD_ARGS)
    assert result.exit_code == 0
    mock_call.assert_not_called()


def test_outcomes_add_backend_mcp_calls_mcp(monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", ":memory:")
    runner = CliRunner()
    with patch("cli.backend._call_mcp") as mock_call:
        mock_call.return_value = "Customer outcome created successfully: {}"
        result = runner.invoke(app, ["--backend", "mcp", *ADD_ARGS])
    assert result.exit_code == 0
    mock_call.assert_called_once()


def test_score_uses_local_backend_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    runner = CliRunner()
    result = runner.invoke(app, ["outcomes", "score", "8", "2"])
    assert result.exit_code == 0
    assert "Opportunity score" in result.output


def test_unknown_backend_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    runner = CliRunner()
    result = runner.invoke(app, ["--backend", "nope", *ADD_ARGS])
    assert result.exit_code != 0
