"""Tests for the `odi summary` report."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _seed(db: str) -> str:
    job = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Deploy a service", "--json"])
    assert job.exit_code == 0, job.output
    job_id = json.loads(job.output)["id"]
    for statement, importance, satisfaction in (
        ("Minimize the time to deploy when a fix is ready", 9, 3),
        ("Maximize the number of services shipped when the team is small", 8, 4),
        ("Minimize the number of rework attempts after a rollback when the release is hot", 4, 4),
    ):
        outcome = runner.invoke(
            app,
            [
                "--db",
                db,
                "desired-outcomes",
                "add",
                "--job-id",
                job_id,
                "--statement",
                statement,
                "--importance",
                str(importance),
                "--satisfaction",
                str(satisfaction),
            ],
        )
        assert outcome.exit_code == 0, outcome.output
    for order in (1, 4):
        step = runner.invoke(
            app,
            [
                "--db",
                db,
                "steps",
                "add",
                "--job-id",
                job_id,
                "--name",
                f"stage {order}",
                "--order",
                str(order),
            ],
        )
        assert step.exit_code == 0, step.output
    return job_id


def test_summary_reports_the_job_and_its_biggest_opportunities(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    job_id = _seed(db)

    result = runner.invoke(app, ["--db", db, "summary", job_id])

    assert result.exit_code == 0, result.output
    assert "Deploy a service" in result.output
    assert "2 of 8 phases (missing 2, 3, 5, 6, 7, 8)" in result.output
    assert "Minimize the time to deploy" in result.output
    assert "15.00" in result.output
    assert "12.00" in result.output
    # A score of 4 is served, so it is not an opportunity.
    assert "rework after a rollback" not in result.output


def test_summary_limits_the_opportunity_list(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    job_id = _seed(db)

    result = runner.invoke(app, ["--db", db, "summary", job_id, "--top", "1"])

    assert result.exit_code == 0, result.output
    assert "15.00" in result.output
    assert "12.00" not in result.output


def test_summary_json_carries_the_coverage_and_ranking(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    job_id = _seed(db)

    result = runner.invoke(app, ["--db", db, "summary", job_id, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["job"]["name"] == "Deploy a service"
    assert payload["step_count"] == 2
    assert payload["outcome_count"] == 3
    assert payload["phase_coverage"] == {
        "covered": [1, 4],
        "missing": [2, 3, 5, 6, 7, 8],
    }
    assert [item["opportunity_score"] for item in payload["underserved"]] == [15.0, 12.0]


def test_summary_reports_a_missing_job(tmp_path) -> None:
    db = str(tmp_path / "odi.db")

    result = runner.invoke(app, ["--db", db, "summary", "JOB-MISSING"])

    assert result.exit_code == 1
    assert "JOB-MISSING" in result.output
