"""Tests for the ``odi candidates`` review subcommands.

The group is the keyboard surface over the review state machine, so these
tests drive the whole path — extract, list, show, accept, reject, merge — and
assert that only ``accept`` creates an outcome.
"""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

VALID = "Minimize the time it takes to onboard a new customer when they sign up."


def _job(runner: CliRunner, db: str, name: str = "Onboard customers") -> str:
    result = runner.invoke(app, ["--db", db, "jobs", "add", "--name", name, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)["id"]


def _extract(runner: CliRunner, db: str, job_id: str, quote: str = VALID) -> list[dict]:
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "candidates",
            "extract",
            "--quote-id",
            "q1",
            "--quote",
            quote,
            "--job-id",
            job_id,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_extract_proposes_without_creating_an_outcome(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)

    proposed = _extract(runner, db, job_id)

    assert len(proposed) == 1
    assert proposed[0]["status"] == "proposed"
    assert proposed[0]["outcome_id"] is None

    outcomes = runner.invoke(app, ["--db", db, "desired-outcomes", "list", "--job-id", job_id])
    assert outcomes.exit_code == 0
    assert "No outcomes found." in outcomes.stdout


def test_extract_reports_an_unknown_job_without_writing(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "candidates",
            "extract",
            "--quote-id",
            "q1",
            "--quote",
            VALID,
            "--job-id",
            "missing",
        ],
    )

    assert result.exit_code == 1
    assert "missing" in result.output


def test_list_renders_a_row_and_filters_by_status(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    _extract(runner, db, job_id)

    listed = runner.invoke(app, ["--db", db, "candidates", "list", "--job-id", job_id])
    assert listed.exit_code == 0
    assert "Minimize the time it takes to onboard" in listed.stdout

    empty = runner.invoke(
        app, ["--db", db, "candidates", "list", "--job-id", job_id, "--status", "rejected"]
    )
    assert empty.exit_code == 0
    assert "No candidates yet." in empty.stdout


def test_show_renders_one_candidate_and_its_json(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    candidate_id = _extract(runner, db, job_id)[0]["id"]

    rendered = runner.invoke(app, ["--db", db, "candidates", "show", candidate_id])
    assert rendered.exit_code == 0
    assert candidate_id in rendered.stdout
    assert "proposed" in rendered.stdout

    as_json = runner.invoke(app, ["--db", db, "candidates", "show", candidate_id, "--json"])
    assert as_json.exit_code == 0
    assert json.loads(as_json.stdout)["id"] == candidate_id


def test_accept_creates_exactly_one_outcome_and_is_then_decided(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    candidate_id = _extract(runner, db, job_id)[0]["id"]

    accepted = runner.invoke(
        app,
        [
            "--db",
            db,
            "candidates",
            "accept",
            candidate_id,
            "--importance",
            "9",
            "--satisfaction",
            "4",
            "--json",
        ],
    )
    assert accepted.exit_code == 0, accepted.output
    outcome = json.loads(accepted.stdout)
    assert outcome["opportunity_score"] == 14.0

    outcomes = runner.invoke(
        app, ["--db", db, "desired-outcomes", "list", "--job-id", job_id, "--json"]
    )
    assert outcomes.exit_code == 0
    assert len(json.loads(outcomes.stdout)) == 1

    again = runner.invoke(
        app,
        [
            "--db",
            db,
            "candidates",
            "accept",
            candidate_id,
            "--importance",
            "9",
            "--satisfaction",
            "4",
        ],
    )
    assert again.exit_code == 1
    assert "already accepted" in again.output


def test_accept_with_an_edited_statement_validates_it(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    candidate_id = _extract(runner, db, job_id)[0]["id"]

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "candidates",
            "accept",
            candidate_id,
            "--importance",
            "5",
            "--satisfaction",
            "5",
            "--statement",
            "This is bad.",
        ],
    )

    assert result.exit_code == 1
    assert "ODI format" in result.output


def test_reject_requires_a_reason_and_keeps_it(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    candidate_id = _extract(runner, db, job_id)[0]["id"]

    rejected = runner.invoke(
        app,
        [
            "--db",
            db,
            "candidates",
            "reject",
            candidate_id,
            "--reason",
            "Not an outcome.",
            "--json",
        ],
    )
    assert rejected.exit_code == 0, rejected.output
    payload = json.loads(rejected.stdout)
    assert payload["status"] == "rejected"
    assert payload["rejection_reason"] == "Not an outcome."

    blank = runner.invoke(
        app, ["--db", db, "candidates", "reject", candidate_id, "--reason", "   "]
    )
    assert blank.exit_code == 1


def test_merge_folds_into_an_existing_outcome_and_creates_none(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    first = _extract(runner, db, job_id)[0]["id"]
    second = _extract(
        runner,
        db,
        job_id,
        quote="Minimize the time it takes to onboard a new customer when they sign up. "
        "Minimize the number of steps it takes to activate a new account when they sign up.",
    )[1]["id"]

    accepted = runner.invoke(
        app,
        [
            "--db",
            db,
            "candidates",
            "accept",
            first,
            "--importance",
            "9",
            "--satisfaction",
            "4",
            "--json",
        ],
    )
    assert accepted.exit_code == 0, accepted.output
    outcome_id = json.loads(accepted.stdout)["id"]

    merged = runner.invoke(
        app,
        [
            "--db",
            db,
            "candidates",
            "merge",
            second,
            "--merged-into",
            outcome_id,
            "--json",
        ],
    )
    assert merged.exit_code == 0, merged.output
    payload = json.loads(merged.stdout)
    assert payload["status"] == "merged"
    assert payload["outcome_id"] == outcome_id

    outcomes = runner.invoke(
        app, ["--db", db, "desired-outcomes", "list", "--job-id", job_id, "--json"]
    )
    assert outcomes.exit_code == 0
    assert len(json.loads(outcomes.stdout)) == 1
