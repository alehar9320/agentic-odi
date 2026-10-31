"""Tests for `odi decide memo` (M3-11/ALH-97).

Pinned choices:

* ``decide memo`` renders the same bytes as the shared ``render_memo``; it does
  not recompute a number or reorder a section.
* A missing section is omitted with its one-line reason, never a zero.
* An unknown decision exits nonzero with a message, no traceback.
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


def _decide(db: str, job_id: str, chosen: str, rejected: str) -> str:
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
            chosen,
            "--reject",
            f"{rejected}=Support cost is already low.",
            "--rationale",
            "The publishing path blocks every release.",
            "--decided-by",
            "dana",
            "--decided-at",
            "2026-01-02T00:00:00Z",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def test_memo_renders_every_section(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0], ids[1])

    result = runner.invoke(app, ["--db", db, "decide", "memo", "--decision-id", decision_id])
    assert result.exit_code == 0, result.output
    for section in (
        "## Decision",
        "## Why now",
        "## What the evidence says",
        "## What we are not doing",
        "## What it is worth",
        "## How we will know",
        "## What we do not know",
        "## Sources",
    ):
        assert section in result.output
    assert "Support cost is already low." in result.output


def test_memo_json_matches_the_markdown(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0], ids[1])

    markdown = runner.invoke(app, ["--db", db, "decide", "memo", "--decision-id", decision_id])
    as_json = runner.invoke(
        app, ["--db", db, "decide", "memo", "--decision-id", decision_id, "--json"]
    )
    assert as_json.exit_code == 0, as_json.output
    payload = json.loads(as_json.output)
    assert payload["decision_id"] == decision_id
    assert payload["markdown"] == markdown.output


def test_memo_omits_a_missing_value_with_a_reason_not_a_zero(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0], ids[1])

    result = runner.invoke(app, ["--db", db, "decide", "memo", "--decision-id", decision_id])
    assert result.exit_code == 0, result.output
    assert "No value estimate recorded" in result.output
    assert "0 currency" not in result.output


def test_memo_unknown_decision_exits_nonzero(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    _seed(db)
    result = runner.invoke(app, ["--db", db, "decide", "memo", "--decision-id", "no-such-decision"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_message_renders_within_budget_and_no_heading(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0], ids[1])

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "decide",
            "message",
            "--decision-id",
            decision_id,
            "--channel",
            "slack",
            "--link",
            "https://example.test/memo",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "https://example.test/memo" in result.output
    assert not any(line.startswith("#") for line in result.output.splitlines())


def test_message_json_carries_the_subject_and_word_count(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0], ids[1])

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "decide",
            "message",
            "--decision-id",
            decision_id,
            "--channel",
            "email",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["subject"].startswith("Decision:")
    assert payload["word_count"] <= 200


def test_message_unknown_decision_exits_nonzero(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    _seed(db)
    result = runner.invoke(
        app,
        ["--db", db, "decide", "message", "--decision-id", "no-such-decision"],
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower()
