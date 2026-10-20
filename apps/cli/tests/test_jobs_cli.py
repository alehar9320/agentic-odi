"""Tests for the Jobs CLI command group."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner


def _add(runner: CliRunner, db: str, *args: str) -> None:
    result = runner.invoke(app, ["--db", db, "jobs", "add", *args])
    assert result.exit_code == 0, result.output


def _list_json(runner: CliRunner, db: str) -> list[dict]:
    result = runner.invoke(app, ["--db", db, "jobs", "list", "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_jobs_add_list_get_round_trip(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    added = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Onboard"])
    assert added.exit_code == 0 and "Job created" in added.output

    listed = runner.invoke(app, ["--db", db, "jobs", "list"])
    assert listed.exit_code == 0 and "Onboard" in listed.output

    jobs = _list_json(runner, db)
    assert len(jobs) == 1
    fetched = runner.invoke(app, ["--db", db, "jobs", "get", jobs[0]["id"], "--json"])
    assert fetched.exit_code == 0
    assert json.loads(fetched.output)["name"] == "Onboard"


def test_jobs_get_unknown_reports_error(tmp_path):
    result = CliRunner().invoke(app, ["--db", str(tmp_path / "odi.db"), "jobs", "get", "nope"])

    assert result.exit_code == 1
    assert "Job not found: nope" in result.output
    assert "Traceback" not in result.output


def test_jobs_get_returns_full_job(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _add(runner, db, "--name", "Write docs", "--description", "draft")
    job_id = _list_json(runner, db)[0]["id"]

    fetched = runner.invoke(app, ["--db", db, "jobs", "get", job_id, "--json"])

    assert fetched.exit_code == 0
    payload = json.loads(fetched.output)
    assert payload["name"] == "Write docs"
    assert payload["description"] == "draft"


def test_jobs_update_only_changes_provided_options(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _add(runner, db, "--name", "Old name", "--description", "keep me")
    job_id = _list_json(runner, db)[0]["id"]

    renamed = runner.invoke(app, ["--db", db, "jobs", "update", job_id, "--name", "New name"])
    assert renamed.exit_code == 0 and "Job updated" in renamed.output
    after = json.loads(runner.invoke(app, ["--db", db, "jobs", "get", job_id, "--json"]).output)
    assert after["name"] == "New name"
    assert after["description"] == "keep me"

    redescribed = runner.invoke(
        app, ["--db", db, "jobs", "update", job_id, "--description", "new desc"]
    )
    assert redescribed.exit_code == 0
    after = json.loads(runner.invoke(app, ["--db", db, "jobs", "get", job_id, "--json"]).output)
    assert after["name"] == "New name"
    assert after["description"] == "new desc"


def test_jobs_update_unknown_reports_error(tmp_path):
    result = CliRunner().invoke(
        app, ["--db", str(tmp_path / "odi.db"), "jobs", "update", "nope", "--name", "X"]
    )

    assert result.exit_code == 1
    assert "Job not found: nope" in result.output


def test_jobs_delete_prompts_then_removes(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _add(runner, db, "--name", "Temp")
    job_id = _list_json(runner, db)[0]["id"]

    declined = runner.invoke(app, ["--db", db, "jobs", "delete", job_id], input="n\n")
    assert declined.exit_code == 0
    assert _list_json(runner, db) != []

    confirmed = runner.invoke(app, ["--db", db, "jobs", "delete", job_id], input="y\n")
    assert confirmed.exit_code == 0 and "Deleted job" in confirmed.output
    assert _list_json(runner, db) == []


def test_jobs_delete_yes_skips_prompt(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _add(runner, db, "--name", "Temp")
    job_id = _list_json(runner, db)[0]["id"]

    result = runner.invoke(app, ["--db", db, "jobs", "delete", job_id, "-y"])

    assert result.exit_code == 0 and "Deleted job" in result.output
    assert "y/N" not in result.output
    assert _list_json(runner, db) == []


def test_jobs_delete_unknown_reports_error(tmp_path):
    result = CliRunner().invoke(
        app, ["--db", str(tmp_path / "odi.db"), "jobs", "delete", "nope", "-y"]
    )

    assert result.exit_code == 1
    assert "Job not found: nope" in result.output


def test_unknown_backend_reports_clear_error():
    result = CliRunner().invoke(app, ["--backend", "nope", "jobs", "list"])

    assert result.exit_code != 0
    assert "unknown backend" in result.output
    assert "Traceback" not in result.output


def test_db_with_mcp_backend_warns(tmp_path, monkeypatch):
    from unittest.mock import patch

    monkeypatch.setenv("AGENTIC_ODI_MCP_URL", "http://example/mcp")
    with patch("agentic_odi_cli.backend._call_mcp", return_value="[]"):
        result = CliRunner().invoke(
            app, ["--backend", "mcp", "--db", str(tmp_path / "odi.db"), "jobs", "list"]
        )

    assert result.exit_code == 0, result.output
    assert "ignored" in result.output.lower()
