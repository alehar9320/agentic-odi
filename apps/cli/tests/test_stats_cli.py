"""`odi stats` — the funnel, printed from the machine that counted it."""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from agentic_odi_core.funnel import (
    FIRST_MESSAGE,
    FIRST_OUTCOME,
    FIRST_SCORE,
    FUNNEL_NAMES,
    record_launch,
    record_milestone,
)
from agentic_odi_core.intent_store import IntentStore
from typer.testing import CliRunner

runner = CliRunner()


def _record_first_session(db_path: str) -> None:
    """Write what one scripted first session writes, through the funnel's own API."""
    store = IntentStore(db_path)
    try:
        record_launch(store, session_id="sess-1")
        record_milestone(store, FIRST_MESSAGE, session_id="sess-1")
        record_milestone(store, FIRST_OUTCOME, session_id="sess-1")
        record_milestone(store, FIRST_SCORE, session_id="sess-1")
    finally:
        store.close()


def _stats(db_path: str, *args: str, input: str | None = None):
    return runner.invoke(app, ["--db", db_path, "--no-update", "stats", *args], input=input)


def test_stats_reports_nothing_for_a_store_that_has_not_been_used(tmp_path) -> None:
    result = _stats(str(tmp_path / "odi.db"))

    assert result.exit_code == 0, result.output
    assert "nothing" in result.output.lower()


def test_stats_prints_every_counter_in_the_vocabulary(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    _record_first_session(db)

    result = _stats(db)

    assert result.exit_code == 0, result.output
    for name in FUNNEL_NAMES:
        assert name in result.output


def test_stats_prints_the_count_beside_each_counter(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    _record_first_session(db)

    result = _stats(db)

    columns = {
        line.split()[0]: line.split()[1]
        for line in result.output.splitlines()
        if line.split() and line.split()[0] in FUNNEL_NAMES
    }
    assert columns == {
        "launch": "1",
        "first_message": "1",
        "first_outcome": "1",
        "first_score": "1",
        "return_session": "0",
    }


def test_stats_prints_the_conversion_between_two_adjacent_steps(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    store = IntentStore(db)
    try:
        record_launch(store, session_id="sess-1")
        record_launch(store, session_id="sess-2")
        record_milestone(store, FIRST_MESSAGE, session_id="sess-2")
    finally:
        store.close()

    result = _stats(db)

    assert "50%" in result.output


def test_stats_json_carries_the_counts_and_the_conversions(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    _record_first_session(db)

    result = _stats(db, "--json")

    assert result.exit_code == 0, result.output
    body = json.loads(result.output)
    assert set(body["events"]) == set(FUNNEL_NAMES)
    assert body["events"]["launch"]["counts"] == 1
    assert body["events"]["return_session"] == {
        "counts": 0,
        "first_seen": None,
        "last_seen": None,
    }
    assert body["conversions"][0]["from"] == "launch"
    assert body["conversions"][0]["to"] == "first_message"
    assert body["conversions"][0]["conversion"] == 1.0


def test_adding_a_scored_outcome_from_the_cli_counts_the_milestones(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    job = runner.invoke(
        app,
        ["--db", db, "--no-update", "jobs", "add", "--name", "Deploy a service", "--json"],
    )
    assert job.exit_code == 0, job.output

    added = runner.invoke(
        app,
        [
            "--db",
            db,
            "--no-update",
            "desired-outcomes",
            "add",
            "--job-id",
            json.loads(job.output)["id"],
            "--statement",
            "Minimize the time to deploy when a fix is ready",
            "--importance",
            "9",
            "--satisfaction",
            "3",
        ],
    )
    assert added.exit_code == 0, added.output

    body = json.loads(_stats(db, "--json").output)
    assert body["events"]["first_outcome"]["counts"] == 1
    assert body["events"]["first_score"]["counts"] == 1


def test_stats_reset_asks_before_it_erases_the_counts(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    _record_first_session(db)

    declined = _stats(db, "--reset", input="\n")

    assert declined.exit_code != 0
    body = json.loads(_stats(db, "--json").output)
    assert body["events"]["first_outcome"]["counts"] == 1


def test_stats_reset_erases_the_counts_when_the_person_confirms(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    _record_first_session(db)

    confirmed = _stats(db, "--reset", input="y\n")

    assert confirmed.exit_code == 0, confirmed.output
    body = json.loads(_stats(db, "--json").output)
    assert all(view["counts"] == 0 for view in body["events"].values())


def test_stats_reset_with_yes_needs_no_answer(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    _record_first_session(db)

    result = _stats(db, "--reset", "--yes")

    assert result.exit_code == 0, result.output
    body = json.loads(_stats(db, "--json").output)
    assert all(view["counts"] == 0 for view in body["events"].values())


def test_stats_names_the_backend_that_has_no_local_log(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    _record_first_session(db)

    result = runner.invoke(
        app, ["--db", db, "--backend", "mcp", "--no-update", "stats"], input=None
    )

    assert result.exit_code == 1
    assert "local" in result.output.lower()
