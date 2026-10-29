"""Tests for the signals CLI group."""

from __future__ import annotations

import json

import pytest
from agentic_odi_cli.cli import app
from typer.testing import CliRunner


@pytest.fixture(autouse=True)
def _default_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTIC_ODI_SIGNAL_BUDGET", raising=False)


def _add_job(runner: CliRunner, db: str, name: str = "Ship a service") -> str:
    result = runner.invoke(app, ["--db", db, "jobs", "add", "--name", name, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def _signal_id(runner: CliRunner, db: str) -> str:
    listed = runner.invoke(app, ["--db", db, "signals", "list", "--json"])
    assert listed.exit_code == 0, listed.output
    return json.loads(listed.output)[0]["id"]


def test_signals_list_shows_the_job_that_was_added(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _add_job(runner, db)

    human = runner.invoke(app, ["--db", db, "signals", "list"])
    assert human.exit_code == 0, human.output
    assert "job_added" in human.output

    listed = runner.invoke(app, ["--db", db, "signals", "list", "--json"])
    payload = json.loads(listed.output)
    assert [item["kind"] for item in payload] == ["job_added"]
    assert payload[0]["subject_id"] == job_id
    assert payload[0]["severity"] == "info"
    assert payload[0]["fingerprint"]


def test_signals_read_removes_it_from_the_unread_view(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _add_job(runner, db)
    signal_id = _signal_id(runner, db)

    read = runner.invoke(app, ["--db", db, "signals", "read", signal_id, "--json"])
    assert read.exit_code == 0, read.output
    assert json.loads(read.output)["read_at"]

    unread = runner.invoke(app, ["--db", db, "signals", "unread", "--json"])
    assert json.loads(unread.output) == []


def test_signals_dismiss_leaves_an_empty_feed(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _add_job(runner, db)
    signal_id = _signal_id(runner, db)

    dismissed = runner.invoke(app, ["--db", db, "signals", "dismiss", signal_id, "--json"])
    assert dismissed.exit_code == 0, dismissed.output
    assert json.loads(dismissed.output)["dismissed_at"]

    listed = runner.invoke(app, ["--db", db, "signals", "list"])
    assert "No signals yet" in listed.output


def test_signals_read_unknown_id_exits_non_zero(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    for command in ("read", "dismiss"):
        result = runner.invoke(app, ["--db", db, "signals", command, "nope"])
        assert result.exit_code == 1, (command, result.output)


def test_signals_list_survives_the_mcp_backend_shape(tmp_path, monkeypatch):
    """The group must resolve through the backend seam like every other command."""
    from agentic_odi_cli import backend as backend_module

    calls: list[tuple[str, dict]] = []

    class _FakeBackend(backend_module.Backend):
        def call(self, tool_name: str, args: dict) -> object:
            calls.append((tool_name, args))
            if tool_name == "list_signals":
                return [{"id": "sig-1", "kind": "job_added", "severity": "info", "title": "t"}]
            return {"id": "sig-1", "read_at": "now"}

    monkeypatch.setattr(backend_module, "require_backend", lambda: _FakeBackend())

    runner = CliRunner()
    listed = runner.invoke(app, ["signals", "list", "--json"])
    assert listed.exit_code == 0, listed.output

    read = runner.invoke(app, ["signals", "read", "sig-1"])
    assert read.exit_code == 0, read.output

    assert calls == [
        ("list_signals", {"unread_only": False, "limit": 50}),
        ("mark_signal_read", {"signal_id": "sig-1"}),
    ]
