"""Tests for desired Outcomes CLI commands."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner


def _job_id(runner: CliRunner, db: str) -> str:
    result = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "J", "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def _add(runner: CliRunner, db: str, job_id: str, *extra: str) -> dict:
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "desired-outcomes",
            "add",
            "--job-id",
            job_id,
            "--statement",
            "Minimize the onboarding time when a customer signs up",
            "--importance",
            "8",
            "--satisfaction",
            "4",
            "--json",
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_outcomes_add_computes_score(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)

    added = _add(runner, db, job_id)

    assert added["opportunity_score"] == 12.0

    listed = runner.invoke(app, ["--db", db, "desired-outcomes", "list", "--job-id", job_id])
    assert (
        listed.exit_code == 0
        and "Minimize the onboarding time when a customer signs up" in listed.output
    )


def test_outcomes_full_lifecycle(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    outcome_id = _add(runner, db, job_id)["id"]

    fetched = runner.invoke(app, ["--db", db, "desired-outcomes", "get", outcome_id, "--json"])
    assert (
        json.loads(fetched.output)["statement"]
        == "Minimize the onboarding time when a customer signs up"
    )

    updated = runner.invoke(
        app,
        ["--db", db, "desired-outcomes", "update", outcome_id, "--importance", "8", "--json"],
    )
    assert updated.exit_code == 0
    assert json.loads(updated.output)["opportunity_score"] == 12.0

    deleted = runner.invoke(app, ["--db", db, "desired-outcomes", "delete", outcome_id, "-y"])
    assert deleted.exit_code == 0 and "Deleted outcome" in deleted.output

    listed = runner.invoke(
        app, ["--db", db, "desired-outcomes", "list", "--job-id", job_id, "--json"]
    )
    assert json.loads(listed.output) == []


def test_outcomes_add_unknown_job_reports_error(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "--db",
            str(tmp_path / "odi.db"),
            "desired-outcomes",
            "add",
            "--job-id",
            "nope",
            "--statement",
            "Minimize the time to ship a release when the build is green",
            "--importance",
            "8",
            "--satisfaction",
            "4",
        ],
    )

    assert result.exit_code == 1
    assert "Job not found: nope" in result.output


def test_outcome_alias_still_points_at_customer_outcomes():
    """`outcomes` stays a backwards-compatible alias for `customer-outcomes`."""

    primary = CliRunner().invoke(app, ["customer-outcomes", "--help"])
    alias = CliRunner().invoke(app, ["outcomes", "--help"])

    assert alias.exit_code == 0
    assert alias.output.splitlines()[0] == primary.output.splitlines()[0]
