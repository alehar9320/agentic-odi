"""ALH-196 (M2-03.1) — ``odi desired-outcomes bulk`` and ``undo`` over the local backend.

A bulk change is reviewable before it lands: the command lists the rows it would write, writes
nothing under ``--dry-run``, hands a token back for the real run, and that token takes the rows
back. The narrowing is the same search the ``search`` command runs, so "everything in this
theme" means every match rather than one page of them.
"""

from __future__ import annotations

import json
from typing import Any

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

STATEMENT_ONE = "Minimize the time it takes to approve an invoice when reconciling"
STATEMENT_TWO = "Minimize the number of mismatches found after close when reconciling"
STATEMENT_THREE = "Maximize the number of exceptions caught before close when reconciling"


def _invoke(runner: CliRunner, db: str, args: list[str]):
    return runner.invoke(app, ["--db", db, *args])


def _json(runner: CliRunner, db: str, args: list[str]) -> Any:
    result = _invoke(runner, db, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _seed(tmp_path, statements: tuple[str, ...] = (STATEMENT_ONE,)) -> tuple[str, str]:
    """A db with one job and the named outcomes; returns (db, job_id)."""
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job = _json(runner, db, ["jobs", "add", "--name", "Reconcile supplier invoices", "--json"])
    job_id = str(job["id"])
    for statement in statements:
        _json(
            runner,
            db,
            [
                "desired-outcomes",
                "add",
                "--job-id",
                job_id,
                "--statement",
                statement,
                "--importance",
                "8",
                "--satisfaction",
                "2",
                "--json",
            ],
        )
    return db, job_id


def _outcome_ids(runner: CliRunner, db: str, job_id: str) -> list[str]:
    page = _json(runner, db, ["desired-outcomes", "list", "--job-id", job_id, "--json"])
    return [str(item["id"]) for item in page]


def _theme(runner: CliRunner, db: str, job_id: str, name: str = "Cash timing") -> str:
    return str(
        _json(runner, db, ["themes", "add", "--name", name, "--job", job_id, "--json"])["id"]
    )


def test_a_dry_run_lists_the_rows_and_writes_nothing(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    outcome_id = _outcome_ids(runner, db, job_id)[0]
    theme_id = _theme(runner, db, job_id)

    report = _json(
        runner,
        db,
        [
            "desired-outcomes",
            "bulk",
            "--id",
            outcome_id,
            "--add-theme",
            theme_id,
            "--dry-run",
            "--json",
        ],
    )

    assert report["requested"] == 1
    assert report["changed"] == [outcome_id]
    assert report["changes"][0] == {
        "outcome_id": outcome_id,
        "field": "theme_ids",
        "from": [],
        "to": [theme_id],
    }
    assert report["undo_token"] is None
    assert _json(runner, db, ["desired-outcomes", "get", outcome_id, "--json"])["theme_ids"] == []


def test_the_preview_reads_as_a_proposal_and_names_the_theme(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    outcome_id = _outcome_ids(runner, db, job_id)[0]
    theme_id = _theme(runner, db, job_id)

    result = _invoke(
        runner,
        db,
        ["desired-outcomes", "bulk", "--id", outcome_id, "--add-theme", theme_id, "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    assert "Would change 1 outcome" in result.output
    assert "Cash timing" in result.output


def test_a_real_run_names_the_token_that_takes_it_back(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    outcome_id = _outcome_ids(runner, db, job_id)[0]
    _theme(runner, db, job_id, "Accuracy")

    result = _invoke(
        runner,
        db,
        [
            "desired-outcomes",
            "bulk",
            "--id",
            outcome_id,
            "--add-theme",
            _theme(runner, db, job_id),
            "--add-tag",
            "needs-review",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Undo with: agentic-odi desired-outcomes undo" in result.output


def test_a_real_run_offers_a_token_and_undo_takes_the_row_back(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    outcome_id = _outcome_ids(runner, db, job_id)[0]
    theme_id = _theme(runner, db, job_id)

    report = _json(
        runner,
        db,
        ["desired-outcomes", "bulk", "--id", outcome_id, "--add-theme", theme_id, "--json"],
    )

    token = report["undo_token"]
    assert token
    assert _json(runner, db, ["desired-outcomes", "get", outcome_id, "--json"])["theme_ids"] == [
        theme_id
    ]

    undone = _json(runner, db, ["desired-outcomes", "undo", token, "--json"])

    assert undone["changed"] == [outcome_id]
    assert _json(runner, db, ["desired-outcomes", "get", outcome_id, "--json"])["theme_ids"] == []


def test_the_undone_token_is_refused_rather_than_replayed(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    outcome_id = _outcome_ids(runner, db, job_id)[0]
    theme_id = _theme(runner, db, job_id)

    token = _json(
        runner,
        db,
        ["desired-outcomes", "bulk", "--id", outcome_id, "--add-theme", theme_id, "--json"],
    )["undo_token"]
    _invoke(runner, db, ["desired-outcomes", "undo", token])

    again = _invoke(runner, db, ["desired-outcomes", "undo", token])

    assert again.exit_code == 1
    assert "already undone" in again.output


def test_a_theme_named_on_both_sides_is_refused_before_anything_is_written(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    outcome_id = _outcome_ids(runner, db, job_id)[0]
    theme_id = _theme(runner, db, job_id)

    result = _invoke(
        runner,
        db,
        [
            "desired-outcomes",
            "bulk",
            "--id",
            outcome_id,
            "--add-theme",
            theme_id,
            "--remove-theme",
            theme_id,
        ],
    )

    assert result.exit_code == 1
    assert "both added and removed" in result.output
    assert _json(runner, db, ["desired-outcomes", "get", outcome_id, "--json"])["theme_ids"] == []


def test_an_explicit_id_and_a_filter_act_on_the_union(tmp_path) -> None:
    db, job_id = _seed(tmp_path, (STATEMENT_ONE, STATEMENT_TWO, STATEMENT_THREE))
    runner = CliRunner()
    ids = _outcome_ids(runner, db, job_id)
    kept, filed = ids[0], ids[1]
    theme_id = _theme(runner, db, job_id)
    _json(
        runner, db, ["desired-outcomes", "bulk", "--id", filed, "--add-theme", theme_id, "--json"]
    )

    report = _json(
        runner,
        db,
        [
            "desired-outcomes",
            "bulk",
            "--id",
            kept,
            "--theme",
            theme_id,
            "--add-tag",
            "needs-review",
            "--json",
        ],
    )

    assert sorted(report["changed"]) == sorted([kept, filed])
    assert _json(runner, db, ["desired-outcomes", "get", kept, "--json"])["tags"] == [
        "needs-review"
    ]


def test_a_filter_applies_to_every_match_not_the_first_page(tmp_path) -> None:
    db, job_id = _seed(tmp_path, (STATEMENT_ONE, STATEMENT_TWO, STATEMENT_THREE))
    runner = CliRunner()
    theme_id = _theme(runner, db, job_id)

    report = _json(
        runner,
        db,
        ["desired-outcomes", "bulk", "--job-id", job_id, "--add-theme", theme_id, "--json"],
    )

    assert report["requested"] == 3
    assert sorted(report["changed"]) == sorted(_outcome_ids(runner, db, job_id))


def test_a_job_without_the_named_stage_skips_that_row_and_reports_why(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    outcome_id = _outcome_ids(runner, db, job_id)[0]

    report = _json(
        runner,
        db,
        ["desired-outcomes", "bulk", "--id", outcome_id, "--set-stage", "execute", "--json"],
    )

    assert report["changed"] == []
    assert report["skipped"] == [{"id": outcome_id, "reason": "job has no stage 'execute'"}]
    assert report["undo_token"] is None


def test_bulk_reports_a_row_that_was_already_right_as_no_change(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    outcome_id = _outcome_ids(runner, db, job_id)[0]
    theme_id = _theme(runner, db, job_id)
    _json(
        runner,
        db,
        ["desired-outcomes", "bulk", "--id", outcome_id, "--add-theme", theme_id, "--json"],
    )

    second = _json(
        runner,
        db,
        ["desired-outcomes", "bulk", "--id", outcome_id, "--add-theme", theme_id, "--json"],
    )

    assert second["changed"] == []
    assert second["skipped"] == [{"id": outcome_id, "reason": "no change"}]
    assert second["undo_token"] is None


def test_bulk_can_narrow_to_a_whole_theme_branch(tmp_path) -> None:
    """``--with-children`` narrows here exactly as it does in ``search``.

    The two commands share one spelling of the filter, so a bulk run cannot quietly act on a
    different set than the one the person just looked at.
    """
    db, job_id = _seed(tmp_path, (STATEMENT_ONE, STATEMENT_TWO))
    runner = CliRunner()
    first, second = _outcome_ids(runner, db, job_id)
    parent = _theme(runner, db, job_id, "Cash timing")
    child = str(
        _json(
            runner,
            db,
            [
                "themes",
                "add",
                "--name",
                "Payment windows",
                "--job",
                job_id,
                "--parent",
                parent,
                "--json",
            ],
        )["id"]
    )
    _json(runner, db, ["themes", "assign", "--theme", parent, "--outcome", first, "--json"])
    _json(runner, db, ["themes", "assign", "--theme", child, "--outcome", second, "--json"])

    own = _json(
        runner,
        db,
        [
            "desired-outcomes",
            "bulk",
            "--theme",
            parent,
            "--add-tag",
            "review",
            "--dry-run",
            "--json",
        ],
    )
    assert own["requested"] == 1

    branch = _json(
        runner,
        db,
        [
            "desired-outcomes",
            "bulk",
            "--theme",
            parent,
            "--with-children",
            "--add-tag",
            "review",
            "--dry-run",
            "--json",
        ],
    )
    assert branch["requested"] == 2
