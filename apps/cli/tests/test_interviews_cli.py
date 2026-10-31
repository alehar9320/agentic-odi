"""Tests for the interviews CLI group (A1)."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner


def _job_id(runner: CliRunner, db: str) -> str:
    result = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Job", "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def _interview_id(runner: CliRunner, db: str, job_id: str) -> str:
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "add",
            "--title",
            "Ana — onboarding",
            "--participant",
            "Ana",
            "--role",
            "Ops lead",
            "--job-id",
            job_id,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def test_interview_add_list_get_delete(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    interview_id = _interview_id(runner, db, job_id)

    listed = runner.invoke(app, ["--db", db, "interviews", "list", "--job-id", job_id, "--json"])
    payload = json.loads(listed.output)
    assert [item["id"] for item in payload] == [interview_id]
    assert payload[0]["participant_label"] == "Ana"

    fetched = runner.invoke(app, ["--db", db, "interviews", "get", interview_id, "--json"])
    assert json.loads(fetched.output)["title"] == "Ana — onboarding"

    deleted = runner.invoke(app, ["--db", db, "interviews", "delete", interview_id, "-y"])
    assert deleted.exit_code == 0 and "Deleted interview" in deleted.output

    empty = runner.invoke(app, ["--db", db, "interviews", "list", "--job-id", job_id, "--json"])
    assert json.loads(empty.output) == []


def test_quotes_command_shows_ordinal_order(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    interview_id = _interview_id(runner, db, job_id)

    # Quotes are added through the local backend tool surface.
    from agentic_odi_cli.backend import LocalBackend

    backend = LocalBackend(db_path=db)
    backend.call("add_quote", {"interview_id": interview_id, "text": "first"})
    backend.call("add_quote", {"interview_id": interview_id, "text": "second"})

    quotes = runner.invoke(app, ["--db", db, "interviews", "quotes", interview_id, "--json"])
    payload = json.loads(quotes.output)
    assert [q["text"] for q in payload] == ["first", "second"]
    assert [q["ordinal"] for q in payload] == [0, 1]


def test_get_missing_interview_reports_not_found(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    result = runner.invoke(app, ["--db", db, "interviews", "get", "missing"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()
