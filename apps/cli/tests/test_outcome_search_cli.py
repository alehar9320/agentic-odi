"""ALH-194 (M2-02.1) — ``desired-outcomes search`` over the local backend.

The ticket asks for ``odi outcomes search``; in this CLI ``outcomes`` is the
hidden alias of ``customer-outcomes``, so the command lives on the desired
group where the outcomes it searches actually live.
"""

from __future__ import annotations

import json
from typing import Any

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

STATEMENT = "Minimize the time it takes to find a payment when reconciling invoices"


def _json(runner: CliRunner, args: list[str]) -> Any:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _seed(tmp_path) -> tuple[str, str, str]:
    """A db with one scored outcome; returns (db, job_id, outcome_id)."""
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job = _json(
        runner,
        ["--db", db, "jobs", "add", "--name", "Reconcile supplier invoices", "--json"],
    )
    job_id = str(job["id"])
    outcome = _json(
        runner,
        [
            "--db",
            db,
            "desired-outcomes",
            "add",
            "--job-id",
            job_id,
            "--statement",
            STATEMENT,
            "--importance",
            "8",
            "--satisfaction",
            "2",
            "--json",
        ],
    )
    return db, job_id, str(outcome["id"])


def test_search_finds_the_outcome_by_statement_text(tmp_path) -> None:
    db, job_id, outcome_id = _seed(tmp_path)

    result = _json(
        CliRunner(), ["--db", db, "desired-outcomes", "search", "--text", "payment", "--json"]
    )

    assert result["total"] == 1
    assert [item["id"] for item in result["items"]] == [outcome_id]
    assert result["facets"]["confidence"] == {"scored": 1, "unscored": 0}


def test_an_impossible_filter_reports_zero_instead_of_everything(tmp_path) -> None:
    db, _, _ = _seed(tmp_path)

    result = _json(
        CliRunner(), ["--db", db, "desired-outcomes", "search", "--text", "zebra", "--json"]
    )

    assert result["items"] == []
    assert result["total"] == 0


def test_search_narrows_by_theme_and_confidence(tmp_path) -> None:
    db, job_id, outcome_id = _seed(tmp_path)
    runner = CliRunner()
    theme = _json(
        runner, ["--db", db, "themes", "add", "--name", "Cash timing", "--job", job_id, "--json"]
    )
    _json(
        runner,
        [
            "--db",
            db,
            "themes",
            "assign",
            "--theme",
            str(theme["id"]),
            "--outcome",
            outcome_id,
            "--json",
        ],
    )

    by_theme = _json(
        runner,
        ["--db", db, "desired-outcomes", "search", "--theme", str(theme["id"]), "--json"],
    )
    assert [item["id"] for item in by_theme["items"]] == [outcome_id]

    missed = _json(
        runner, ["--db", db, "desired-outcomes", "search", "--confidence", "unscored", "--json"]
    )
    assert missed["total"] == 0

    band = _json(runner, ["--db", db, "desired-outcomes", "search", "--min-score", "100", "--json"])
    assert band["total"] == 0


def test_search_scopes_to_one_job(tmp_path) -> None:
    """``--job-id`` is spelled like every other command in this group."""
    db, job_id, outcome_id = _seed(tmp_path)
    runner = CliRunner()
    other = _json(runner, ["--db", db, "jobs", "add", "--name", "Onboard a supplier", "--json"])

    mine = _json(runner, ["--db", db, "desired-outcomes", "search", "--job-id", job_id, "--json"])
    assert [item["id"] for item in mine["items"]] == [outcome_id]

    theirs = _json(
        runner,
        ["--db", db, "desired-outcomes", "search", "--job-id", str(other["id"]), "--json"],
    )
    assert theirs["items"] == []
    assert theirs["total"] == 0


def test_a_malformed_query_fails_as_an_error_not_a_crash(tmp_path) -> None:
    db, _, _ = _seed(tmp_path)

    result = CliRunner().invoke(
        app, ["--db", db, "desired-outcomes", "search", "--stage", "sidestep"]
    )

    assert result.exit_code == 1
    assert "sidestep" in result.output


def test_the_human_rendering_names_the_counts(tmp_path) -> None:
    db, _, _ = _seed(tmp_path)

    result = CliRunner().invoke(
        app, ["--db", db, "desired-outcomes", "search", "--text", "payment"]
    )

    assert result.exit_code == 0
    assert "1" in result.output and STATEMENT.split()[1] in result.output

    empty = CliRunner().invoke(app, ["--db", db, "desired-outcomes", "search", "--text", "zebra"])
    assert "nothing matches" in empty.output.lower()
