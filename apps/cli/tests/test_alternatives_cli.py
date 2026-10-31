"""Alternatives CLI: local backend, output, solution state, and errors (M2-07)."""

from __future__ import annotations

import json
import re

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

ANSI = re.compile(r"\x1b\[[0-9;]*m")
runner = CliRunner()


def _strip(text: str) -> str:
    return ANSI.sub("", text)


def _seed(db_path: str) -> None:
    """Alternatives validate their Job and Outcome, so seed both up front."""
    from agentic_odi_core import Job, ODIService
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    repo = SQLiteRepository(db_path=db_path)
    if repo.get_job("job-1") is None:
        repo.add_job(Job(id="job-1", name="Onboard customers"))
    service = ODIService(repo)
    if not service.get_outcomes("job-1"):
        service.add_outcome(
            "job-1",
            "Minimize the time it takes to onboard a customer when they sign up",
            importance=8.0,
            satisfaction=4.0,
        )


def _outcome_id(db_path: str) -> str:
    from agentic_odi_core import ODIService
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    return ODIService(SQLiteRepository(db_path=db_path)).get_outcomes("job-1")[0].id


def _add_alternative(db_path: str, *, name: str = "Spreadsheet", kind: str = "manual") -> str:
    added = runner.invoke(
        app,
        [
            "--backend",
            "local",
            "--db",
            db_path,
            "alternatives",
            "add",
            "--job-id",
            "job-1",
            "--name",
            name,
            "--kind",
            kind,
        ],
    )
    assert added.exit_code == 0, added.output
    return json.loads(
        runner.invoke(
            app, ["--backend", "local", "--db", db_path, "alternatives", "list", "--json"]
        ).output
    )[-1]["id"]


def test_help_lists_subcommands():
    result = runner.invoke(app, ["alternatives", "--help"])
    assert result.exit_code == 0
    output = _strip(result.output)
    for command in ("add", "list", "link", "show"):
        assert command in output


def test_add_then_list_round_trips(tmp_path):
    db = str(tmp_path / "odi.db")
    _seed(db)
    _add_alternative(db)
    listed = runner.invoke(app, ["--backend", "local", "--db", db, "alternatives", "list"])
    assert listed.exit_code == 0
    output = _strip(listed.output)
    assert "Spreadsheet" in output
    assert "manual" in output


def test_linking_a_spreadsheet_reports_yes(tmp_path):
    db = str(tmp_path / "odi.db")
    _seed(db)
    alternative_id = _add_alternative(db)
    outcome_id = _outcome_id(db)
    linked = runner.invoke(
        app,
        [
            "--backend",
            "local",
            "--db",
            db,
            "alternatives",
            "link",
            outcome_id,
            alternative_id,
            "--adequacy",
            "7",
        ],
    )
    assert linked.exit_code == 0, linked.output
    shown = runner.invoke(
        app, ["--backend", "local", "--db", db, "alternatives", "show", outcome_id]
    )
    assert shown.exit_code == 0
    assert "Existing solution: yes" in _strip(shown.output)


def test_a_nothing_row_reports_no_linked_nothing(tmp_path):
    db = str(tmp_path / "odi.db")
    _seed(db)
    alternative_id = _add_alternative(db, name="Nothing today", kind="nothing")
    outcome_id = _outcome_id(db)
    runner.invoke(
        app,
        [
            "--backend",
            "local",
            "--db",
            db,
            "alternatives",
            "link",
            outcome_id,
            alternative_id,
            "--adequacy",
            "1",
        ],
    )
    shown = runner.invoke(
        app, ["--backend", "local", "--db", db, "alternatives", "show", outcome_id]
    )
    assert "no — the customer uses nothing today" in _strip(shown.output)


def test_an_uninventoried_outcome_is_not_no_solution(tmp_path):
    db = str(tmp_path / "odi.db")
    _seed(db)
    outcome_id = _outcome_id(db)
    shown = runner.invoke(
        app, ["--backend", "local", "--db", db, "alternatives", "show", outcome_id]
    )
    assert shown.exit_code == 0
    output = _strip(shown.output)
    assert "Not yet inventoried" in output
    assert "we have not asked" in output


def test_unknown_job_is_refused(tmp_path):
    db = str(tmp_path / "odi.db")
    _seed(db)
    result = runner.invoke(
        app,
        [
            "--backend",
            "local",
            "--db",
            db,
            "alternatives",
            "add",
            "--job-id",
            "missing",
            "--name",
            "X",
            "--kind",
            "product",
        ],
    )
    assert result.exit_code != 0
    assert "not found" in _strip(result.output).lower()
