"""Tests for the evidence CLI group."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner


def _job_id(runner: CliRunner, db: str) -> str:
    result = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Job", "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def _add_evidence(runner: CliRunner, db: str, job_id: str, content: str = "Slow setup") -> str:
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "evidence",
            "add",
            "--source-name",
            "gong",
            "--source-kind",
            "mcp",
            "--name",
            "feedback",
            "--content",
            content,
            "--job-id",
            job_id,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def test_evidence_add_list_get_delete(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    evidence_id = _add_evidence(runner, db, job_id)

    listed = runner.invoke(app, ["--db", db, "evidence", "list", "--job-id", job_id, "--json"])
    payload = json.loads(listed.output)
    assert [item["id"] for item in payload] == [evidence_id]
    assert payload[0]["content"] == "Slow setup"

    fetched = runner.invoke(app, ["--db", db, "evidence", "get", evidence_id, "--json"])
    assert json.loads(fetched.output)["source_name"] == "gong"

    deleted = runner.invoke(app, ["--db", db, "evidence", "delete", evidence_id, "-y"])
    assert deleted.exit_code == 0 and "Deleted evidence" in deleted.output

    empty = runner.invoke(app, ["--db", db, "evidence", "list", "--job-id", job_id, "--json"])
    assert json.loads(empty.output) == []


def test_evidence_add_unknown_job_reports_error(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "--db",
            str(tmp_path / "odi.db"),
            "evidence",
            "add",
            "--source-name",
            "gong",
            "--name",
            "feedback",
            "--content",
            "quote",
            "--job-id",
            "nope",
        ],
    )

    assert result.exit_code == 1
    assert "Job not found: nope" in result.output


def test_evidence_promote_to_job_and_outcome(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    evidence_id = _add_evidence(runner, db, job_id)

    promoted_job = runner.invoke(
        app,
        ["--db", db, "evidence", "promote", evidence_id, "--to", "job"],
    )
    assert promoted_job.exit_code == 0
    assert "Job created" in promoted_job.output

    promoted_outcome = runner.invoke(
        app,
        [
            "--db",
            db,
            "evidence",
            "promote",
            evidence_id,
            "--to",
            "outcome",
            "--job-id",
            job_id,
            "--statement",
            "Minimize the time to set up when onboarding",
            "--importance",
            "8",
            "--satisfaction",
            "4",
        ],
    )
    assert promoted_outcome.exit_code == 0
    assert "Outcome created" in promoted_outcome.output
