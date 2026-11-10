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


def test_message_copy_falls_back_to_printing_when_no_clipboard(tmp_path, monkeypatch) -> None:
    """--copy never fails the command: with no clipboard tool it prints instead."""
    from agentic_odi_cli import decide

    monkeypatch.setattr(decide.shutil, "which", lambda _name: None)
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0], ids[1])

    result = runner.invoke(
        app,
        ["--db", db, "decide", "message", "--decision-id", decision_id, "--copy"],
    )
    assert result.exit_code == 0, result.output
    assert "No clipboard tool found" in result.output
    assert "We found an unmet need" in result.output


def test_message_verbose_reports_a_dropped_sentence(tmp_path) -> None:
    """A long rationale drops the action sentence and reports it under --verbose."""
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    long_rationale = " ".join(f"reason{i}" for i in range(130))
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
            ids[0],
            "--reject",
            f"{ids[1]}=Support cost is already low.",
            "--rationale",
            long_rationale,
            "--decided-by",
            "dana",
            "--decided-at",
            "2026-01-02T00:00:00Z",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    decision_id = json.loads(result.output)["id"]

    message = runner.invoke(
        app,
        ["--db", db, "decide", "message", "--decision-id", decision_id, "--verbose"],
    )
    assert message.exit_code == 0, message.output
    assert "dropped for length" in message.output
    assert "action" in message.output


# ------------------------------------------ export + narrate (M3-11.2/ALH-171)


def test_memo_html_export_is_standalone_and_carries_the_schema_version(tmp_path) -> None:
    from agentic_odi_core import SCHEMA_VERSION

    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0], ids[1])

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "decide",
            "memo",
            "--decision-id",
            decision_id,
            "--format",
            "html",
            "--generated-at",
            "2026-10-29T12:00:00Z",
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.output.startswith("<!DOCTYPE html>")
    assert "<style>" in result.output
    assert "Exported from the recorded data" in result.output
    assert f"Schema version: {SCHEMA_VERSION}" in result.output
    assert "2026-10-29T12:00:00Z" in result.output
    assert "http://" not in result.output and "https://" not in result.output


def test_memo_default_export_is_unchanged_markdown(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0], ids[1])

    default = runner.invoke(app, ["--db", db, "decide", "memo", "--decision-id", decision_id])
    explicit = runner.invoke(
        app, ["--db", db, "decide", "memo", "--decision-id", decision_id, "--no-narrate"]
    )
    assert default.exit_code == 0 and explicit.exit_code == 0
    assert default.output == explicit.output
    assert default.output.startswith("# Decision memo")


def test_memo_export_writes_to_out_path(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0], ids[1])
    destination = tmp_path / "memo.md"

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "decide",
            "memo",
            "--decision-id",
            decision_id,
            "--out",
            str(destination),
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.output.strip() == str(destination)
    assert destination.read_text(encoding="utf-8").startswith("# Decision memo")


def test_memo_unknown_format_exits_nonzero(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0], ids[1])
    result = runner.invoke(
        app, ["--db", db, "decide", "memo", "--decision-id", decision_id, "--format", "pdf"]
    )
    assert result.exit_code != 0
    assert "unknown format" in result.output.lower()


def test_memo_unwritable_destination_exits_nonzero(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0], ids[1])
    missing_dir = tmp_path / "nope" / "memo.md"
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "decide",
            "memo",
            "--decision-id",
            decision_id,
            "--out",
            str(missing_dir),
        ],
    )
    assert result.exit_code != 0
    assert "could not write" in result.output.lower()
    assert not missing_dir.exists()


def test_memo_narrate_without_a_provider_still_exports_and_reports(tmp_path, monkeypatch) -> None:
    """--narrate with no provider keeps the factual memo and says why the block is absent."""

    def _no_provider(cls=None):
        raise RuntimeError("no provider configured")

    monkeypatch.setattr(
        "agentic_odi_cli.narrator.OpenAINarrator.from_env", classmethod(_no_provider)
    )
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    decision_id = _decide(db, job_id, ids[0], ids[1])

    result = runner.invoke(
        app,
        ["--db", db, "decide", "memo", "--decision-id", decision_id, "--narrate"],
    )
    assert result.exit_code == 0, result.output
    assert result.output.startswith("# Decision memo")
    assert "narrator failed" in result.output or "no narrator configured" in result.output
