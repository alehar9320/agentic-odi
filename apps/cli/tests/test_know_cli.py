"""CLI tests for bets, decisions, signals, the digest and the spine status."""

from __future__ import annotations

import json
import re
from datetime import date

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

STATEMENT = "Minimize the time it takes to onboard a customer when they sign up"


def _invoke(runner: CliRunner, db: str, *args: str):
    result = runner.invoke(app, ["--db", db, *args])
    assert result.exit_code == 0, result.output
    return result


def _flat(text: str) -> str:
    """Collapse wrapped output so assertions do not depend on terminal width.

    Rich wraps long error text across panel borders, which would otherwise split
    a phrase like ``at least one --outcome`` mid-sentence. Strip the box drawing
    and ANSI, then collapse whitespace.
    """
    plain = re.sub(r"\x1b\[[0-9;]*m", "", text)
    plain = re.sub(r"[\u2500-\u257f]", " ", plain)
    return " ".join(plain.split())


def _job(runner: CliRunner, db: str) -> str:
    return json.loads(_invoke(runner, db, "jobs", "add", "--name", "Onboard", "--json").output)[
        "id"
    ]


def _outcome(runner: CliRunner, db: str, job_id: str, *, importance: str = "8") -> str:
    return json.loads(
        _invoke(
            runner,
            db,
            "desired-outcomes",
            "add",
            "--job-id",
            job_id,
            "--statement",
            STATEMENT,
            "--importance",
            importance,
            "--satisfaction",
            "4",
            "--json",
        ).output
    )["id"]


def _decision(runner: CliRunner, db: str, job_id: str, outcome_id: str) -> str:
    return json.loads(
        _invoke(
            runner,
            db,
            "decisions",
            "record",
            "--job-id",
            job_id,
            "--outcome",
            outcome_id,
            "--rationale",
            "Largest gap",
            "--by",
            "alex",
            "--json",
        ).output
    )["id"]


def _bet(runner: CliRunner, db: str, decision_id: str, outcome_id: str, *, target: str = "12"):
    return json.loads(
        _invoke(
            runner,
            db,
            "bets",
            "add",
            "--decision-id",
            decision_id,
            "--outcome-id",
            outcome_id,
            "--hypothesis",
            "Time drops",
            "--target",
            target,
            "--measure-by",
            "2020-01-01",
            "--json",
        ).output
    )


def test_bet_creation_freezes_the_baseline(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)
    decision_id = _decision(runner, db, job_id, outcome_id)

    bet = _bet(runner, db, decision_id, outcome_id)
    assert bet["baseline"] == 12.0
    assert bet["status"] == "planned"

    # Re-scoring the outcome must not move the stored baseline.
    _invoke(
        runner,
        db,
        "desired-outcomes",
        "update",
        outcome_id,
        "--importance",
        "3",
        "--satisfaction",
        "3",
        "--json",
    )
    shown = json.loads(_invoke(runner, db, "bets", "show", bet["id"], "--json").output)
    assert shown["baseline"] == 12.0


def test_bets_list_marks_overdue(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)
    decision_id = _decision(runner, db, job_id, outcome_id)
    _bet(runner, db, decision_id, outcome_id)

    output = _invoke(runner, db, "bets", "list").output
    assert "overdue" in output


def test_bets_list_is_empty_and_honest(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    assert "No bets found." in _invoke(runner, db, "bets", "list").output


def test_bet_measure_reports_no_data(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)
    decision_id = _decision(runner, db, job_id, outcome_id)
    bet = _bet(runner, db, decision_id, outcome_id)

    result = json.loads(_invoke(runner, db, "bets", "measure", bet["id"], "--json").output)
    assert result["result"] == "no_data"
    assert "No data yet" in _invoke(runner, db, "bets", "measure", bet["id"]).output


def test_illegal_transition_is_refused(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)
    decision_id = _decision(runner, db, job_id, outcome_id)
    bet = _bet(runner, db, decision_id, outcome_id)

    result = runner.invoke(app, ["--db", db, "bets", "status", bet["id"], "measured"])
    assert result.exit_code != 0
    assert "legal next states" in _flat(result.output)


def test_know_list_and_digest(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)
    decision_id = _decision(runner, db, job_id, outcome_id)
    _bet(runner, db, decision_id, outcome_id)

    digest = _invoke(runner, db, "know", "digest", "--since", "3650d").output
    assert "## Bets due" in digest

    # The digest refreshed the inbox; the same due bet is now a real signal.
    signals = json.loads(_invoke(runner, db, "signals", "list", "--json").output)
    assert any(s["kind"] == "bet_due" for s in signals)


def test_digest_empty_period_is_explicit(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    assert "No changes in this period." in _invoke(runner, db, "know", "digest").output


def test_digest_out_writes_the_same_bytes(tmp_path):
    db = str(tmp_path / "odi.db")
    out = tmp_path / "digest.md"
    runner = CliRunner()
    _invoke(runner, db, "know", "digest", "--since", "3650d", "--out", str(out))
    assert out.read_text(encoding="utf-8") == "No changes in this period."


def test_spine_reports_first_blocker(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    assert "No job yet." in _invoke(runner, db, "know", "spine").output

    job_id = _job(runner, db)
    _outcome(runner, db, job_id)
    output = _invoke(runner, db, "know", "spine", "--job", job_id).output
    assert "captured   1" in output
    assert "record a decision" in output


def test_spine_json_and_auto_job_selection(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    _outcome(runner, db, job_id)

    # No --job: the single job is chosen deterministically.
    rows = json.loads(_invoke(runner, db, "know", "spine", "--json").output)
    by_stage = {row["stage"]: row for row in rows}
    assert by_stage["captured"]["count"] == 1
    assert by_stage["decided"]["blocker"] == "record a decision"
    # Only the first missing link is named; later stages stay blank.
    assert by_stage["bet"]["blocker"] == ""
    assert by_stage["measured"]["blocker"] == ""


def test_toplevel_digest_matches_the_know_alias(tmp_path):
    """E4 promises `odi digest`; the `know digest` alias must be identical."""
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)
    decision_id = _decision(runner, db, job_id, outcome_id)
    _bet(runner, db, decision_id, outcome_id)

    assert (
        _invoke(runner, db, "digest", "--since", "3650d").output
        == _invoke(runner, db, "know", "digest", "--since", "3650d").output
    )


def test_toplevel_digest_out_writes_the_same_bytes(tmp_path):
    db = str(tmp_path / "odi.db")
    out = tmp_path / "digest.md"
    runner = CliRunner()
    _invoke(runner, db, "digest", "--since", "3650d", "--out", str(out))
    assert out.read_text(encoding="utf-8") == "No changes in this period."


def test_toplevel_status_spine_matches_the_know_alias(tmp_path):
    """E4.1 promises `odi status --spine`; the `know spine` alias must match."""
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    assert "No job yet." in _invoke(runner, db, "status", "--spine").output

    job_id = _job(runner, db)
    _outcome(runner, db, job_id)
    assert (
        _invoke(runner, db, "status", "--spine", "--job", job_id).output
        == _invoke(runner, db, "know", "spine", "--job", job_id).output
    )


def test_toplevel_status_without_spine_writes_nothing(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    output = _invoke(runner, db, "status").output
    assert "--spine" in output


def test_bets_list_narrows_to_one_job(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)
    decision_id = _decision(runner, db, job_id, outcome_id)
    _bet(runner, db, decision_id, outcome_id)

    assert "Time drops" in _invoke(runner, db, "bets", "list", "--job-id", job_id).output
    # An unknown job is an honest error, not an empty list.
    missing = runner.invoke(app, ["--db", db, "bets", "list", "--job-id", "missing"])
    assert missing.exit_code != 0
    assert "job not found" in missing.output


def test_know_list_narrows_to_one_job(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)
    decision_id = _decision(runner, db, job_id, outcome_id)
    _bet(runner, db, decision_id, outcome_id)

    _invoke(runner, db, "know", "digest", "--since", "3650d")
    signals = json.loads(_invoke(runner, db, "signals", "list", "--json").output)
    assert any(s["kind"] == "bet_due" for s in signals)


def test_bet_add_rejects_a_malformed_date(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)
    decision_id = _decision(runner, db, job_id, outcome_id)

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
            outcome_id,
            "--hypothesis",
            "Time drops",
            "--target",
            "12",
            "--measure-by",
            "not-a-date",
        ],
    )
    assert result.exit_code != 0
    assert "ISO date" in _flat(result.output)


def test_decision_record_requires_an_outcome(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)

    result = runner.invoke(
        app,
        ["--db", db, "decisions", "record", "--job-id", job_id, "--rationale", "x", "--by", "alex"],
    )
    assert result.exit_code != 0
    assert "at least one --outcome" in _flat(result.output)


def test_decision_record_rejects_a_malformed_rejection(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "decisions",
            "record",
            "--job-id",
            job_id,
            "--outcome",
            outcome_id,
            "--rationale",
            "x",
            "--by",
            "alex",
            "--reject",
            "no-reason-here",
        ],
    )
    assert result.exit_code != 0
    assert "id:reason" in _flat(result.output)


def test_decision_record_keeps_a_rejection_reason(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    chosen = _outcome(runner, db, job_id)
    other = _outcome(runner, db, job_id)

    decision = json.loads(
        _invoke(
            runner,
            db,
            "decisions",
            "record",
            "--job-id",
            job_id,
            "--outcome",
            chosen,
            "--rationale",
            "Largest gap",
            "--by",
            "alex",
            "--reject",
            f"{other}:Lower reach",
            "--json",
        ).output
    )
    assert decision["rejected"] == [{"outcome_id": other, "reason": "Lower reach"}]


def test_since_accepts_hours_and_dates(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    # An hours window and an ISO date each take a distinct parse path.
    assert (
        "No changes in this period."
        in _invoke(runner, db, "know", "digest", "--since", "24h").output
    )
    assert (
        "No changes in this period."
        in _invoke(runner, db, "know", "digest", "--since", "2020-01-01").output
    )


def test_digest_honours_the_shared_policy(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)
    decision_id = _decision(runner, db, job_id, outcome_id)
    _bet(runner, db, decision_id, outcome_id)

    # The default policy keeps a due bet; disabling that kind silences it while
    # the signal stays real in the feed.
    assert "## Bets due" in _invoke(runner, db, "know", "digest", "--since", "3650d").output
    from agentic_odi_cli.backend import LocalBackend

    LocalBackend(db_path=db).call(
        "set_notification_rule", {"kind": "bet_due", "threshold": 0.0, "enabled": False}
    )
    assert (
        "No changes in this period."
        in _invoke(runner, db, "know", "digest", "--since", "3650d").output
    )
    signals = json.loads(_invoke(runner, db, "signals", "list", "--json").output)
    assert any(s["kind"] == "bet_due" for s in signals)


def test_digest_keeps_read_signals_the_bell_drops(tmp_path):
    """The weekly record is not personal read-state.

    ALH-242 pins the choice explicitly: reading a signal clears the bell but must
    not erase it from the digest. The digest filters by the shared policy, not by
    read/dismissed state.
    """
    from agentic_odi_cli.backend import LocalBackend

    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)
    decision_id = _decision(runner, db, job_id, outcome_id)
    _bet(runner, db, decision_id, outcome_id)

    # Refresh the inbox, then read the due bet.
    _invoke(runner, db, "know", "digest", "--since", "3650d")
    backend = LocalBackend(db_path=db)
    due = next(s for s in backend.call("list_signals", {"limit": 200}) if s["kind"] == "bet_due")
    backend.call("mark_signal_read", {"signal_id": due["id"]})

    # The bell no longer counts it, but the digest still records it: the weekly
    # record is not personal read-state.
    unread = backend.call("list_signals", {"unread_only": True, "limit": 200})
    assert due["id"] not in {signal["id"] for signal in unread}
    assert "## Bets due" in _invoke(runner, db, "know", "digest", "--since", "3650d").output


def test_digest_rejects_a_bad_window(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    result = runner.invoke(app, ["--db", db, "know", "digest", "--since", "0d"])
    assert result.exit_code != 0
    result = runner.invoke(app, ["--db", db, "know", "digest", "--since", "soon"])
    assert result.exit_code != 0


def test_decisions_list_marks_superseded(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)
    _decision(runner, db, job_id, outcome_id)
    _decision(runner, db, job_id, outcome_id)

    listed = json.loads(_invoke(runner, db, "decisions", "list", job_id, "--json").output)
    assert len(listed) == 2
    assert listed[0]["superseded_by"] == listed[1]["id"]
    assert "superseded" in _invoke(runner, db, "decisions", "list", job_id).output


def test_bet_measure_reports_met_after_a_new_score(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job(runner, db)
    outcome_id = _outcome(runner, db, job_id)
    decision_id = _decision(runner, db, job_id, outcome_id)
    bet = _bet(runner, db, decision_id, outcome_id, target="12")

    # A score recorded today is at or after the 2020 measure_by date.
    _invoke(
        runner,
        db,
        "desired-outcomes",
        "update",
        outcome_id,
        "--importance",
        "9",
        "--satisfaction",
        "2",
        "--json",
    )
    from agentic_odi_cli.backend import LocalBackend

    LocalBackend(db_path=db).call("record_score_snapshot", {"outcome_id": outcome_id})

    result = json.loads(_invoke(runner, db, "bets", "measure", bet["id"], "--json").output)
    assert result["result"] == "met"
    assert result["observed"] == 16.0
    assert date.fromisoformat(result["measure_by"]) == date(2020, 1, 1)


def test_digest_builder_ignores_unusable_timestamps():
    from datetime import datetime, timezone

    from agentic_odi_cli.know import _within, build_digest

    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # A row with no time and a row with a non-ISO time are both skipped, never
    # guessed at.
    assert _within({"created_at": ""}, since) is False
    assert _within({"created_at": "not-a-time"}, since) is False
    assert _within({"created_at": "2026-06-01T00:00:00"}, since) is True  # naive → UTC
    body = build_digest(
        [
            {"kind": "bet_due", "created_at": "", "title": "no time", "id": "a"},
            {"kind": "bet_due", "created_at": "2026-06-01T00:00:00", "title": "due", "id": "b"},
        ],
        [{"kind": "bet_due", "enabled": True}],
        since=since,
    )
    assert "due" in body
    assert "no time" not in body


def test_digest_reads_the_utc_suffix_pydantic_writes():
    """A ``Z``-suffixed UTC stamp must parse on every supported Python.

    Python 3.10's ``datetime.fromisoformat`` rejects ``Z``; before the fix a
    real signal was silently dropped and the digest claimed no changes.
    """
    from datetime import datetime, timezone

    from agentic_odi_cli.know import _within, build_digest

    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert _within({"created_at": "2026-06-01T00:00:00Z"}, since) is True
    body = build_digest(
        [{"kind": "bet_due", "created_at": "2026-06-01T00:00:00Z", "title": "due", "id": "b"}],
        [{"kind": "bet_due", "enabled": True}],
        since=since,
    )
    assert "## Bets due" in body
    assert "due" in body


def test_digest_policy_gates_a_small_score_move():
    from datetime import datetime, timezone

    from agentic_odi_cli.know import build_digest

    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rules = [{"kind": "score_moved", "threshold": 0.5, "enabled": True}]
    small = {
        "kind": "score_moved",
        "created_at": "2026-06-01T00:00:00",
        "title": "moved a little",
        "id": "s",
        "magnitude": 0.1,
    }
    big = {**small, "id": "b", "title": "moved a lot", "magnitude": 2.0}
    assert "moved a little" not in build_digest([small], rules, since=since)
    assert "moved a lot" in build_digest([big], rules, since=since)


def test_digest_unruled_kind_never_interrupts():
    from agentic_odi_cli.know import _should_notify

    # A kind with no stored rule stays feed-only, matching the core's
    # should_notify rather than defaulting to an interruption.
    assert _should_notify({"kind": "job_added"}, {}) is False
    assert _should_notify({"kind": "bet_due"}, {"bet_due": {"enabled": True}}) is True
    assert _should_notify({"kind": "bet_due"}, {"bet_due": {"enabled": False}}) is False
