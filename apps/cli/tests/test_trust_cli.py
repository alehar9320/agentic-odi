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


def test_survey_import_dry_run_writes_nothing_and_reports_lines(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    added = _add(runner, db, job_id)

    csv_path = tmp_path / "responses.csv"
    csv_path.write_text(
        f"outcome_id,importance,satisfaction\n{added['id']},8,4\nghost,8,4\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["--db", db, "survey", "import", str(csv_path), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "Would import 1 of 2 row(s)" in result.output
    assert "line 3 [unmatched]" in result.output

    # The dry run wrote nothing: the outcome is still unscored.
    shown = runner.invoke(app, ["--db", db, "desired-outcomes", "get", added["id"], "--json"])
    assert json.loads(shown.output)["score_method"] == "estimate"  # unchanged


def test_survey_import_refuses_a_partial_write(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    added = _add(runner, db, job_id)

    csv_path = tmp_path / "responses.csv"
    csv_path.write_text(
        f"outcome_id,importance,satisfaction\n{added['id']},8,4\nghost,8,4\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["--db", db, "survey", "import", str(csv_path)])
    assert result.exit_code != 0
    assert "unresolved row" in result.output

    shown = runner.invoke(app, ["--db", db, "desired-outcomes", "get", added["id"], "--json"])
    assert json.loads(shown.output)["score_method"] == "estimate"  # unchanged


def test_survey_dry_run_names_every_unmatched_row(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    added = _add(runner, db, job_id)

    csv_path = tmp_path / "responses.csv"
    csv_path.write_text(
        f"outcome_id,importance,satisfaction\n{added['id']},8,4\nghost-a,8,4\nghost-b,8,4\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["--db", db, "survey", "import", str(csv_path), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "line 3 [unmatched]" in result.output
    assert "line 4 [unmatched]" in result.output


def test_survey_dry_run_rejects_a_zero_at_its_line(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    added = _add(runner, db, job_id)

    csv_path = tmp_path / "responses.csv"
    csv_path.write_text(
        f"outcome_id,importance,satisfaction\n{added['id']},0,4\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["--db", db, "survey", "import", str(csv_path), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "line 2 [invalid]" in result.output
    assert "between 1 and 10" in result.output


def test_survey_line_numbers_survive_a_quoted_multiline_record(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    _add(runner, db, job_id)

    csv_path = tmp_path / "responses.csv"
    # A quoted statement spans physical lines 2-3, so the ghost row starts at 4.
    csv_path.write_text(
        "outcome_statement,importance,satisfaction\n"
        '"A statement that\nspans two lines",8,4\n'
        "ghost,8,4\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["--db", db, "survey", "import", str(csv_path), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "line 4 [unmatched]" in result.output


def test_survey_match_without_confirmation_fails_safely(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    added = _add(runner, db, job_id)

    csv_path = tmp_path / "responses.csv"
    # "GHOST" normalizes to the real id, so a suggestion exists but is unconfirmed.
    csv_path.write_text(
        f"outcome_id,importance,satisfaction\n{added['id'].upper()},8,4\n",
        encoding="utf-8",
    )
    # No stdin: the confirmation prompt aborts rather than auto-accepting.
    result = runner.invoke(app, ["--db", db, "survey", "import", str(csv_path), "--match"])
    assert result.exit_code != 0

    shown = runner.invoke(app, ["--db", db, "desired-outcomes", "get", added["id"], "--json"])
    assert json.loads(shown.output)["score_method"] == "estimate"  # unchanged


def test_survey_match_writes_when_every_row_already_resolves(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    added = _add(runner, db, job_id)

    csv_path = tmp_path / "responses.csv"
    rows = "".join(f"{added['id']},8,4\n" for _ in range(40))
    csv_path.write_text("outcome_id,importance,satisfaction\n" + rows, encoding="utf-8")

    result = runner.invoke(app, ["--db", db, "survey", "import", str(csv_path), "--match"])
    assert result.exit_code == 0, result.output

    shown = runner.invoke(app, ["--db", db, "desired-outcomes", "get", added["id"], "--json"])
    assert json.loads(shown.output)["score_method"] == "survey"


def test_survey_match_confirms_and_writes(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    added = _add(runner, db, job_id)

    csv_path = tmp_path / "responses.csv"
    # The id differs only in case, so it is proposed but not auto-accepted.
    rows = "".join(f"{added['id'].upper()},8,4\n" for _ in range(40))
    csv_path.write_text("outcome_id,importance,satisfaction\n" + rows, encoding="utf-8")

    result = runner.invoke(
        app, ["--db", db, "survey", "import", str(csv_path), "--match"], input="y\n"
    )
    assert result.exit_code == 0, result.output

    shown = runner.invoke(app, ["--db", db, "desired-outcomes", "get", added["id"], "--json"])
    payload = json.loads(shown.output)
    assert payload["score_method"] == "survey"
    assert payload["importance_n"] == 40


def test_survey_dry_run_leaves_the_store_unchanged(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    added = _add(runner, db, job_id)

    csv_path = tmp_path / "responses.csv"
    rows = "".join(f"{added['id']},8,4\n" for _ in range(40))
    csv_path.write_text("outcome_id,importance,satisfaction\n" + rows, encoding="utf-8")

    result = runner.invoke(app, ["--db", db, "survey", "import", str(csv_path), "--dry-run"])
    assert result.exit_code == 0, result.output

    # No score landed and no snapshot was added: only the initial add remains.
    shown = json.loads(
        runner.invoke(app, ["--db", db, "desired-outcomes", "get", added["id"], "--json"]).output
    )
    assert shown["score_method"] == "estimate"
    assert shown["importance"] == 8.0
    history = json.loads(
        runner.invoke(
            app, ["--db", db, "desired-outcomes", "history", added["id"], "--json"]
        ).output
    )
    assert len(history) == 1  # just the initial add; the dry run added none


def test_survey_import_reports_an_unreadable_path(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    missing = tmp_path / "nope.csv"
    result = runner.invoke(app, ["--db", db, "survey", "import", str(missing)])
    assert result.exit_code != 0
    assert "cannot read" in result.output
