"""Tests for the candidates CLI group and the interviews extract command (A4)."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

QUOTE = "Setup takes forever when a new hire starts."


def _interview_with_quote(runner: CliRunner, db: str) -> tuple[str, str]:
    job = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Onboard", "--json"])
    job_id = json.loads(job.output)["id"]
    interview = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "add",
            "--title",
            "T",
            "--participant",
            "Ana",
            "--job-id",
            job_id,
            "--json",
        ],
    )
    interview_id = json.loads(interview.output)["id"]
    from agentic_odi_cli.backend import LocalBackend

    backend = LocalBackend(db_path=db)
    quote_id = backend.call("add_quote", {"interview_id": interview_id, "text": QUOTE})["id"]
    return interview_id, quote_id


def test_extract_then_list_and_get(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    interview_id, quote_id = _interview_with_quote(runner, db)

    extracted = runner.invoke(app, ["--db", db, "interviews", "extract", quote_id, "--json"])
    assert extracted.exit_code == 0, extracted.output
    candidates = json.loads(extracted.output)
    assert candidates

    listed = runner.invoke(
        app, ["--db", db, "candidates", "list", "--interview-id", interview_id, "--json"]
    )
    assert len(json.loads(listed.output)) == len(candidates)

    candidate_id = candidates[0]["id"]
    fetched = runner.invoke(app, ["--db", db, "candidates", "get", candidate_id, "--json"])
    assert json.loads(fetched.output)["id"] == candidate_id


def test_extract_is_idempotent(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _, quote_id = _interview_with_quote(runner, db)

    runner.invoke(app, ["--db", db, "interviews", "extract", quote_id, "--json"])
    second = runner.invoke(app, ["--db", db, "interviews", "extract", quote_id, "--json"])
    assert json.loads(second.output) == []


def test_list_filters_by_status(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _, quote_id = _interview_with_quote(runner, db)
    runner.invoke(app, ["--db", db, "interviews", "extract", quote_id, "--json"])

    proposed = runner.invoke(
        app, ["--db", db, "candidates", "list", "--status", "proposed", "--json"]
    )
    assert all(c["status"] == "proposed" for c in json.loads(proposed.output))


def test_delete_candidate(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _, quote_id = _interview_with_quote(runner, db)
    candidate_id = json.loads(
        runner.invoke(app, ["--db", db, "interviews", "extract", quote_id, "--json"]).output
    )[0]["id"]

    deleted = runner.invoke(app, ["--db", db, "candidates", "delete", candidate_id, "-y"])
    assert deleted.exit_code == 0
    assert "Deleted outcome candidate" in deleted.output

    missing = runner.invoke(app, ["--db", db, "candidates", "get", candidate_id])
    assert missing.exit_code != 0
    assert "not found" in missing.output.lower()


def test_extract_unknown_quote_reports_not_found(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    result = runner.invoke(app, ["--db", db, "interviews", "extract", "missing"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()
