"""ALH-65 (M2-01) — the ``themes`` CLI group over the local backend."""

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
    """A db with one job and one outcome; returns (db, job_id, outcome_id)."""
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


def test_themes_list_is_empty_before_the_first_theme(tmp_path) -> None:
    db, _, _ = _seed(tmp_path)
    assert _json(CliRunner(), ["--db", db, "themes", "list", "--json"]) == []


def test_add_rename_and_delete_walk_the_theme_tree(tmp_path) -> None:
    db, job_id, _ = _seed(tmp_path)
    runner = CliRunner()

    parent = _json(
        runner, ["--db", db, "themes", "add", "--name", "Cash timing", "--job", job_id, "--json"]
    )
    child = _json(
        runner,
        [
            "--db",
            db,
            "themes",
            "add",
            "--name",
            "Payment windows",
            "--job",
            job_id,
            "--parent",
            str(parent["id"]),
            "--json",
        ],
    )
    renamed = _json(
        runner,
        [
            "--db",
            db,
            "themes",
            "rename",
            str(child["id"]),
            "--name",
            "Payment timing",
            "--json",
        ],
    )
    assert renamed["name"] == "Payment timing"
    assert renamed["parent_id"] == parent["id"]

    deleted = _json(runner, ["--db", db, "themes", "delete", str(parent["id"]), "--json"])
    assert deleted["reparented"] == [child["id"]]

    listed = _json(runner, ["--db", db, "themes", "list", "--job", job_id, "--json"])
    assert [theme["parent_id"] for theme in listed] == [None]


def test_a_third_level_theme_exits_nonzero(tmp_path) -> None:
    db, job_id, _ = _seed(tmp_path)
    runner = CliRunner()
    parent = _json(
        runner, ["--db", db, "themes", "add", "--name", "Cash timing", "--job", job_id, "--json"]
    )
    child = _json(
        runner,
        [
            "--db",
            db,
            "themes",
            "add",
            "--name",
            "Payment windows",
            "--job",
            job_id,
            "--parent",
            str(parent["id"]),
            "--json",
        ],
    )

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "themes",
            "add",
            "--name",
            "Too deep",
            "--job",
            job_id,
            "--parent",
            str(child["id"]),
        ],
    )

    assert result.exit_code == 1
    assert "two levels" in result.output


def test_assign_and_unassign_move_memberships(tmp_path) -> None:
    db, job_id, outcome_id = _seed(tmp_path)
    runner = CliRunner()
    theme = _json(
        runner, ["--db", db, "themes", "add", "--name", "Cash timing", "--job", job_id, "--json"]
    )
    theme_id = str(theme["id"])

    assigned = _json(
        runner,
        ["--db", db, "themes", "assign", "--theme", theme_id, "--outcome", outcome_id, "--json"],
    )
    assert assigned[0]["theme_ids"] == [theme_id]

    _json(
        runner,
        ["--db", db, "themes", "unassign", "--theme", theme_id, "--outcome", outcome_id, "--json"],
    )
    stored = _json(runner, ["--db", db, "desired-outcomes", "get", outcome_id, "--json"])
    assert stored["theme_ids"] == []


def test_unknown_job_is_reported_not_raised(tmp_path) -> None:
    db, _, _ = _seed(tmp_path)
    result = CliRunner().invoke(
        app, ["--db", db, "themes", "add", "--name", "Orphan", "--job", "no-such-job"]
    )
    assert result.exit_code == 1
    assert "not found" in result.output
