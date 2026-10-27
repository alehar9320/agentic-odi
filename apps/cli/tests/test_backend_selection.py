from unittest.mock import patch

from agentic_odi_cli.cli import app
from typer.testing import CliRunner


def _seed_job(db_path: str, job_id: str = "job-1") -> None:
    """Customer Outcomes validate their parent Job, so seed one first."""
    from agentic_odi_core import Job
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    SQLiteRepository(db_path=db_path).add_job(Job(id=job_id, name="Onboard customers"))


ADD_ARGS = [
    "customer-outcomes",
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


def test_customer_outcomes_add_defaults_to_local(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    _seed_job(str(tmp_path / "odi.db"))
    runner = CliRunner()
    with patch("agentic_odi_cli.backend._call_mcp") as mock_call:
        result = runner.invoke(app, ADD_ARGS)
    assert result.exit_code == 0
    mock_call.assert_not_called()


def test_customer_outcomes_add_backend_mcp_calls_mcp(monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", ":memory:")
    runner = CliRunner()
    with patch("agentic_odi_cli.backend._call_mcp") as mock_call:
        mock_call.return_value = "Customer outcome created successfully: {}"
        result = runner.invoke(app, ["--backend", "mcp", *ADD_ARGS])
    assert result.exit_code == 0
    mock_call.assert_called_once()


def test_score_uses_local_backend_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    runner = CliRunner()
    result = runner.invoke(app, ["score", "8", "2"])
    assert result.exit_code == 0
    assert "Opportunity score" in result.output


def test_score_backend_mcp_calls_mcp(monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", ":memory:")
    runner = CliRunner()
    with patch("agentic_odi_cli.backend._call_mcp") as mock_call:
        mock_call.return_value = "Opportunity score: 14.00"
        result = runner.invoke(app, ["--backend", "mcp", "score", "8", "2"])
    assert result.exit_code == 0
    mock_call.assert_called_once()


def test_unknown_backend_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    runner = CliRunner()
    result = runner.invoke(app, ["--backend", "nope", *ADD_ARGS])
    assert result.exit_code != 0
