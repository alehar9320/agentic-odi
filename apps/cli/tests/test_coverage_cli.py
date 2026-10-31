"""Tests for the coverage CLI command (A8 / ALH-21)."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

VALID = "Minimize the time it takes to onboard a customer when they sign up"


def _job(runner: CliRunner, db: str, name: str = "Onboard") -> str:
    result = runner.invoke(app, ["--db", db, "jobs", "add", "--name", name])
    assert result.exit_code == 0, result.output
    return json.loads(runner.invoke(app, ["--db", db, "jobs", "list", "--json"]).output)[-1]["id"]


def _step(runner: CliRunner, db: str, job_id: str, order: int, stage: str) -> str:
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "steps",
            "add",
            "--job-id",
            job_id,
            "--name",
            stage,
            "--order",
            str(order),
            "--stage",
            stage,
            "--allow-empty-job-map",
        ],
    )
    assert result.exit_code == 0, result.output
    steps = json.loads(
        runner.invoke(app, ["--db", db, "steps", "list", "--job-id", job_id, "--json"]).output
    )
    return steps[-1]["id"]


def _outcome(runner: CliRunner, db: str, job_id: str, step_id: str | None) -> None:
    args = [
        "--db",
        db,
        "desired-outcomes",
        "add",
        "--job-id",
        job_id,
        "--statement",
        VALID,
        "--importance",
        "8",
        "--satisfaction",
        "4",
    ]
    if step_id:
        args += ["--step-id", step_id]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output


def test_coverage_json_has_all_eight_stages_in_order(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)

    result = runner.invoke(app, ["--db", db, "coverage", job_id, "--json"])

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert [row["stage"] for row in report["per_stage"]] == [
        "define",
        "locate",
        "prepare",
        "confirm",
        "execute",
        "monitor",
        "modify",
        "conclude",
    ]
    assert report["gaps"] == [row["stage"] for row in report["per_stage"]]


def test_coverage_table_names_the_gaps(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)

    result = runner.invoke(app, ["--db", db, "coverage", job_id])

    assert result.exit_code == 0, result.output
    assert "Define" in result.output
    assert "Gaps:" in result.output
    assert "Unassigned:" in result.output


def test_coverage_unknown_job_reports_error(tmp_path):
    result = CliRunner().invoke(app, ["--db", str(tmp_path / "odi.db"), "coverage", "nope"])

    assert result.exit_code == 1
    assert "Job not found: nope" in result.output
    assert "Traceback" not in result.output


def test_coverage_define_and_locate_reports_six_gaps(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    define = _step(runner, db, job_id, 1, "define")
    locate = _step(runner, db, job_id, 2, "locate")
    _outcome(runner, db, job_id, define)
    _outcome(runner, db, job_id, locate)

    result = runner.invoke(app, ["--db", db, "coverage", job_id, "--json"])

    report = json.loads(result.output)
    assert report["gaps"] == [
        "prepare",
        "confirm",
        "execute",
        "monitor",
        "modify",
        "conclude",
    ]
