"""Tests for `odi review show` and `odi bets` (C8/E1.2, ALH-39/ALH-159).

Pinned choices:

* ``review show`` renders the same bytes as the shared ``render_review``; it
  does not recompute a delta or a day count.
* ``--today`` pins the clock so the day count is reproducible.
* A missing measurement stays ``no evidence``, never ``no change``; a deleted
  outcome is ``orphaned``.
* ``bets add`` captures the baseline at creation; the CLI never recomputes it.
* ``bets advance`` refuses an illegal transition and names the legal ones.
* A malformed ``--today`` and an unknown decision exit nonzero, no traceback.
"""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _seed(db: str) -> tuple[str, list[str]]:
    job = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Publish a plugin", "--json"])
    assert job.exit_code == 0, job.output
    job_id = json.loads(job.output)["id"]
    ids = []
    for statement, importance, satisfaction in (
        ("Minimize the time it takes to publish a plugin when a release is ready", 9, 3),
        ("Minimize the cost of supporting a plugin when it ships", 5, 7),
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
                "--json",
            ],
        )
        assert outcome.exit_code == 0, outcome.output
        ids.append(json.loads(outcome.output)["id"])
    return job_id, ids


def _decide(db: str, job_id: str, outcome_id: str, decided_at: str = "2026-11-15T00:00:00Z") -> str:
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "decide",
            "record",
            "--job-id",
            job_id,
            "--choose",
            outcome_id,
            "--rationale",
            "The publishing path blocks every release.",
            "--decided-by",
            "dana",
            "--decided-at",
            decided_at,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def _rescore(db: str, outcome_id: str, satisfaction: float, at: str) -> None:
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "desired-outcomes",
            "update",
            outcome_id,
            "--satisfaction",
            str(satisfaction),
            "--at",
            at,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output


def test_review_show_reports_a_rise_and_the_elapsed_days(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0])
    _rescore(db, ids[0], 5.1, "2026-12-01T00:00:00Z")

    result = runner.invoke(
        app,
        ["--db", db, "review", "show", "--decision-id", decision_id, "--today", "2027-01-30"],
    )

    assert result.exit_code == 0, result.output
    assert "# Decision review" in result.output
    assert "improved" in result.output
    assert "+2.1" in result.output
    assert "76 day(s) ago" in result.output


def test_review_show_json_emits_the_projection(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0])

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "review",
            "show",
            "--decision-id",
            decision_id,
            "--today",
            "2027-01-30",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["decision_id"] == decision_id
    assert payload["days_elapsed"] == 76
    assert payload["outcomes"][0]["state"] == "no change"


def test_review_show_refuses_a_malformed_today(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0])

    result = runner.invoke(
        app,
        ["--db", db, "review", "show", "--decision-id", decision_id, "--today", "soon"],
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "ISO-8601" in result.output


def test_review_show_unknown_decision_exits_nonzero(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    result = runner.invoke(
        app, ["--db", db, "review", "show", "--decision-id", "DEC-NOPE", "--today", "2027-01-30"]
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "DEC-NOPE" in result.output


def test_bets_add_captures_the_baseline_and_advances(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0])

    added = runner.invoke(
        app,
        [
            "--db",
            db,
            "bets",
            "add",
            "--decision-id",
            decision_id,
            "--outcome-id",
            ids[0],
            "--hypothesis",
            "Publishing gets under five minutes",
            "--target",
            "6.0",
            "--measure-by",
            "2026-04-01",
            "--json",
        ],
    )
    assert added.exit_code == 0, added.output
    bet = json.loads(added.output)
    assert bet["baseline"] == 15.0
    assert bet["status"] == "planned"

    _rescore(db, ids[0], 9.0, "2026-12-01T00:00:00Z")
    shown = runner.invoke(app, ["--db", db, "bets", "show", "--bet-id", bet["id"], "--json"])
    assert json.loads(shown.output)["baseline"] == 15.0

    running = runner.invoke(
        app, ["--db", db, "bets", "advance", "--bet-id", bet["id"], "--status", "running"]
    )
    assert running.exit_code == 0, running.output
    assert "running" in running.output

    listed = runner.invoke(app, ["--db", db, "bets", "list", "--job-id", job_id])
    assert listed.exit_code == 0, listed.output
    assert bet["id"] in listed.output


def test_bets_list_reports_the_empty_state(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    result = runner.invoke(app, ["--db", db, "bets", "list"])
    assert result.exit_code == 0, result.output
    assert "No bets recorded yet." in result.output


def test_bets_advance_refuses_an_illegal_transition(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0])
    bet = json.loads(
        runner.invoke(
            app,
            [
                "--db",
                db,
                "bets",
                "add",
                "--decision-id",
                decision_id,
                "--outcome-id",
                ids[0],
                "--hypothesis",
                "h",
                "--target",
                "6.0",
                "--measure-by",
                "2026-04-01",
                "--json",
            ],
        ).output
    )

    result = runner.invoke(
        app, ["--db", db, "bets", "advance", "--bet-id", bet["id"], "--status", "measured"]
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "running" in result.output and "abandoned" in result.output


def test_bets_add_refuses_a_bet_for_an_unchosen_outcome(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0])

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "bets",
            "add",
            "--decision-id",
            decision_id,
            "--outcome-id",
            ids[1],
            "--hypothesis",
            "h",
            "--target",
            "6.0",
            "--measure-by",
            "2026-04-01",
        ],
    )
    assert result.exit_code != 0
    assert "not one the decision" in result.output
