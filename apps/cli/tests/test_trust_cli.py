"""Tests for the trust surfaces: survey import, deltas, top and coverage."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner


def _job_id(runner: CliRunner, db: str) -> str:
    result = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Job", "--json"])
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


def test_history_why_shows_a_signed_delta(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    added = _add(runner, db, job_id)

    updated = runner.invoke(
        app,
        [
            "--db",
            db,
            "desired-outcomes",
            "update",
            added["id"],
            "--satisfaction",
            "6",
            "--json",
        ],
    )
    assert updated.exit_code == 0, updated.output

    result = runner.invoke(app, ["--db", db, "desired-outcomes", "history", added["id"], "--why"])
    assert result.exit_code == 0, result.output
    assert "Change:" in result.output


def test_history_why_json_carries_a_direction(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    added = _add(runner, db, job_id)
    runner.invoke(
        app, ["--db", db, "desired-outcomes", "update", added["id"], "--satisfaction", "6"]
    )

    result = runner.invoke(
        app, ["--db", db, "desired-outcomes", "history", added["id"], "--why", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    delta = payload["delta"]
    assert delta["direction"] in {"up", "down", "flat"}
    assert delta["outcome_id"] == added["id"]
    assert len(payload["history"]) == 2


def test_survey_import_lands_a_mean_and_band(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    added = _add(runner, db, job_id)

    csv_path = tmp_path / "responses.csv"
    header = "outcome_id,importance,satisfaction\n"
    rows = "".join(f"{added['id']},8,4\n" for _ in range(40))
    csv_path.write_text(header + rows, encoding="utf-8")

    result = runner.invoke(app, ["--db", db, "survey", "import", str(csv_path), "--json"])
    assert result.exit_code == 0, result.output
    updated = json.loads(result.output)
    assert updated[added["id"]]["importance_n"] == 40
    assert updated[added["id"]]["score_method"] == "survey"
    assert updated[added["id"]]["opportunity_low"] is not None


def test_survey_import_reports_an_unmatched_file(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("outcome_id,importance,satisfaction\n", encoding="utf-8")

    result = runner.invoke(app, ["--db", db, "survey", "import", str(csv_path)])
    assert result.exit_code != 0
    assert "no rows" in result.output


def test_top_excludes_thin_and_unscored_by_default(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    measured = _add(
        runner, db, job_id, "--importance-n", "40", "--satisfaction-n", "40", "--method", "survey"
    )
    _add(runner, db, job_id)

    result = runner.invoke(app, ["--db", db, "top", "--job", job_id, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [entry["id"] for entry in payload["measured"]] == [measured["id"]]
    assert payload["excluded"]["none"] == 1


def test_coverage_counts_every_outcome(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    _add(runner, db, job_id, "--importance-n", "40", "--satisfaction-n", "40", "--method", "survey")
    _add(runner, db, job_id, "--importance-n", "3", "--satisfaction-n", "3", "--method", "survey")
    _add(runner, db, job_id)

    result = runner.invoke(app, ["--db", db, "coverage", "--job", job_id, "--json"])
    assert result.exit_code == 0, result.output
    counts = json.loads(result.output)
    assert counts == {"measured": 1, "thin": 1, "none": 1, "total": 3}
