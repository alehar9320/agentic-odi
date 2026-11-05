"""The next step at the terminal (ALH-146, M0-14).

A session that ends with "I'll talk to two support leads" currently loses that
intention to the browser. These tests prove the terminal can make the promise,
read back the one that is outstanding, answer it with what happened — and reach
all of it through the ``run_tool`` backend seam like every other command, never
by touching the service directly.
"""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from agentic_odi_core.models import NextStep
from typer.testing import CliRunner


def _json(runner: CliRunner, args: list[str]) -> object:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_show_names_nothing_until_a_step_is_set(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    shown = runner.invoke(app, ["--db", db, "next-step", "show"])

    assert shown.exit_code == 0, shown.output
    assert "No next step" in shown.output
    assert "odi next-step set" in shown.output


def test_set_then_show_reads_the_same_step_back(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    step = _json(
        runner,
        ["--db", db, "next-step", "set", "Talk to two support leads", "--json"],
    )
    assert step["text"] == "Talk to two support leads"  # type: ignore[index]
    assert NextStep.model_validate(step).is_open is True

    shown = _json(runner, ["--db", db, "next-step", "show", "--json"])
    assert shown["id"] == step["id"]  # type: ignore[index]

    human = runner.invoke(app, ["--db", db, "next-step", "show"])
    assert "Talk to two support leads" in human.output
    # A field the user never filled reads as nothing, not as the word "None".
    assert "None" not in human.output


def test_a_second_step_replaces_the_first_instead_of_joining_it(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    first = _json(runner, ["--db", db, "next-step", "set", "Talk to two support leads", "--json"])
    second = _json(
        runner, ["--db", db, "next-step", "set", "Ask the payer what they do today", "--json"]
    )

    # The greeting must read exactly one, so `show` cannot offer a choice.
    shown = _json(runner, ["--db", db, "next-step", "show", "--json"])
    assert shown["id"] == second["id"]  # type: ignore[index]
    # And the first is kept as history rather than deleted.
    listed = _json(runner, ["--db", db, "next-step", "list", "--json"])
    assert {item["id"] for item in listed} == {first["id"], second["id"]}  # type: ignore[index]


def test_resolve_answers_the_step_and_keeps_what_happened(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    step = _json(runner, ["--db", db, "next-step", "set", "Talk to two support leads", "--json"])

    record = _json(
        runner,
        [
            "--db",
            db,
            "next-step",
            "resolve",
            str(step["id"]),  # type: ignore[index]
            "Both still hand-carry the spreadsheet",
            "--json",
        ],
    )
    assert record["content"] == "Both still hand-carry the spreadsheet"  # type: ignore[index]
    assert record["raw"]["next_step_id"] == step["id"]  # type: ignore[index]

    # Nothing is outstanding now, and the answer survives in the library.
    shown = runner.invoke(app, ["--db", db, "next-step", "show"])
    assert "No next step" in shown.output
    evidence = _json(runner, ["--db", db, "evidence", "list", "--json"])
    assert record["id"] in [item["id"] for item in evidence]  # type: ignore[index]


def test_resolve_refuses_an_unknown_step(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    missing = runner.invoke(app, ["--db", db, "next-step", "resolve", "not-a-step", "Did it"])

    assert missing.exit_code == 1
    assert "next step not found" in missing.output.lower()


def test_later_moves_the_when_without_claiming_anything_happened(tmp_path):
    """``later`` is the honest answer to "not yet": the row moves, nothing is learned.

    A bare date is what a person types, and the store records a reminder as a
    moment, so the terminal supplies the timezone it is standing in rather than
    refusing the input.
    """
    from datetime import datetime

    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    step = _json(runner, ["--db", db, "next-step", "set", "Draft the interview guide", "--json"])

    moved = _json(
        runner, ["--db", db, "next-step", "later", str(step["id"]), "2026-12-01", "--json"]
    )  # noqa: E501

    assert moved["id"] == step["id"]  # type: ignore[index]
    when = datetime.fromisoformat(moved["due_at"])  # type: ignore[arg-type]
    assert when.year == 2026 and when.month == 12 and when.day == 1
    assert when.tzinfo is not None
    assert moved["resolved_at"] is None and moved["superseded_at"] is None  # type: ignore[index]
    assert _json(runner, ["--db", db, "evidence", "list", "--json"]) == []


def test_drop_closes_the_step_and_records_no_answer(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    step = _json(runner, ["--db", db, "next-step", "set", "Draft the interview guide", "--json"])

    dropped = _json(runner, ["--db", db, "next-step", "drop", str(step["id"]), "--json"])

    assert dropped["superseded_at"] is not None  # type: ignore[index]
    assert dropped["resolved_at"] is None  # type: ignore[index]
    shown = runner.invoke(app, ["--db", db, "next-step", "show"])
    assert "No next step" in shown.output
    assert _json(runner, ["--db", db, "evidence", "list", "--json"]) == []


def test_next_step_commands_resolve_through_the_backend_seam(monkeypatch):
    from agentic_odi_cli import backend as backend_module

    calls: list[tuple[str, dict]] = []
    step = {
        "id": "ns-1",
        "text": "Talk to two support leads",
        "created_at": "2026-01-01T00:00:00+00:00",
        "due_at": None,
        "resolved_at": None,
        "resolution": None,
        "superseded_at": None,
        "outcome_id": None,
    }
    record = {
        "id": "ev-1",
        "source_name": "You (next step)",
        "source_kind": "manual",
        "item_type": "manual",
        "name": "Next step — Talk to two support leads",
        "content": "Both still hand-carry the spreadsheet",
        "url": None,
        "raw": {"next_step_id": "ns-1", "origin": "user"},
        "job_id": None,
        "step_id": None,
        "outcome_id": None,
    }

    class _FakeBackend(backend_module.Backend):
        def call(self, tool_name: str, args: dict) -> object:
            calls.append((tool_name, args))
            if tool_name == "list_next_steps":
                return [step]
            if tool_name == "resolve_next_step":
                return record
            return step

    monkeypatch.setattr(backend_module, "require_backend", lambda: _FakeBackend())

    runner = CliRunner()
    assert runner.invoke(app, ["next-step", "set", "Talk to two support leads"]).exit_code == 0
    assert runner.invoke(app, ["next-step", "show"]).exit_code == 0
    assert runner.invoke(app, ["next-step", "list"]).exit_code == 0
    assert runner.invoke(app, ["next-step", "resolve", "ns-1", "Did it"]).exit_code == 0
    assert runner.invoke(app, ["next-step", "later", "ns-1", "2026-12-01"]).exit_code == 0
    assert runner.invoke(app, ["next-step", "drop", "ns-1"]).exit_code == 0

    assert [name for name, _ in calls] == [
        "set_next_step",
        "get_next_step",
        "list_next_steps",
        "resolve_next_step",
        "reschedule_next_step",
        "drop_next_step",
    ]
