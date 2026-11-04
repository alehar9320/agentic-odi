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


# --- the rollup (ALH-163) --------------------------------------------------

TOP = "Minimize the time to match a remittance when closing a month"
SECOND = "Minimize the number of invoices chased before the week closes"
THIRD = "Minimize the number of exceptions a reviewer handles while closing"
FOURTH = "Minimize the time a feed waits to be checked when it arrives"


def _add_outcome(
    runner: CliRunner,
    db: str,
    job_id: str,
    statement: str,
    scores: tuple[str, str],
) -> str:
    args = [
        "--db",
        db,
        "desired-outcomes",
        "add",
        "--job-id",
        job_id,
        "--statement",
        statement,
        "--importance",
        scores[0],
        "--satisfaction",
        scores[1],
    ]
    return str(_json(runner, [*args, "--json"])["id"])


def _import_unscored(
    tmp_path, runner: CliRunner, db: str, job_id: str, statements: tuple[str, ...]
) -> list[str]:
    """Rows carrying no scores: ``add`` demands a score, so an unmeasured outcome arrives here.

    That is the library's real shape — a spreadsheet row nobody has rated yet — and it is what
    makes a theme with a top of nothing worth testing.
    """
    document = tmp_path / "unscored.csv"
    document.write_text(
        "statement\n" + "".join(f'"{text}"\n' for text in statements), encoding="utf-8"
    )
    report = _json(
        runner,
        ["--db", db, "desired-outcomes", "import", str(document), "--job-id", job_id, "--json"],
    )
    return [str(row["outcome_id"]) for row in report["created"]]


def _add_theme(
    runner: CliRunner,
    db: str,
    job_id: str,
    name: str,
    *,
    parent: str | None = None,
    ordinal: int = 0,
) -> str:
    args = ["--db", db, "themes", "add", "--name", name, "--job", job_id]
    if parent is not None:
        args += ["--parent", parent]
    if ordinal:
        args += ["--ordinal", str(ordinal)]
    return str(_json(runner, [*args, "--json"])["id"])


def _file(runner: CliRunner, db: str, theme_id: str, *outcome_ids: str) -> None:
    args = ["--db", db, "themes", "assign", "--theme", theme_id]
    for outcome_id in outcome_ids:
        args += ["--outcome", outcome_id]
    _json(runner, [*args, "--json"])


def _branch(tmp_path) -> tuple[str, dict[str, str]]:
    """A tree where one outcome sits in the parent *and* in both children.

    That overlap is the point: the parent's own two plus the children's two and two sum to six,
    and the honest answer for the branch is four.
    """
    db, job_id, _ = _seed(tmp_path)
    runner = CliRunner()
    top = _add_outcome(runner, db, job_id, TOP, ("9", "1"))
    second = _add_outcome(runner, db, job_id, SECOND, ("6", "4"))
    third, fourth = _import_unscored(tmp_path, runner, db, job_id, (THIRD, FOURTH))
    parent = _add_theme(runner, db, job_id, "Cash timing")
    windows = _add_theme(runner, db, job_id, "Payment windows", parent=parent, ordinal=1)
    cutoffs = _add_theme(runner, db, job_id, "Cut-off times", parent=parent, ordinal=2)
    empty = _add_theme(runner, db, job_id, "Bank feeds", ordinal=1)
    unscored = _add_theme(runner, db, job_id, "Unreviewed", ordinal=2)
    _file(runner, db, parent, top, second)
    _file(runner, db, windows, top, third)
    _file(runner, db, cutoffs, top, fourth)
    _file(runner, db, unscored, third)
    return db, {
        "job_id": job_id,
        "parent": parent,
        "windows": windows,
        "cutoffs": cutoffs,
        "empty": empty,
        "unscored": unscored,
    }


def _rollup(runner: CliRunner, db: str, args: list[str]):
    return runner.invoke(app, ["--db", db, "themes", "rollup", *args])


def test_a_parent_counts_its_branch_as_one_set_not_a_sum(tmp_path) -> None:
    db, branch = _branch(tmp_path)

    result = _rollup(CliRunner(), db, [branch["parent"]])

    assert result.exit_code == 0, result.output
    assert "Cash timing" in result.output
    assert "4 outcome(s)" in result.output
    assert "2 measured" in result.output
    assert "17.00" in result.output
    assert "remittance when closing a month" in result.output
    assert "6 outcome" not in result.output, "the union of ids, never the sum of the children"


def test_a_child_counts_only_what_is_filed_under_it(tmp_path) -> None:
    db, branch = _branch(tmp_path)

    result = _rollup(CliRunner(), db, [branch["windows"]])

    assert result.exit_code == 0, result.output
    assert "Payment windows" in result.output
    assert "2 outcome(s)" in result.output
    assert "1 measured" in result.output


def test_an_empty_theme_says_so_instead_of_counting_zero(tmp_path) -> None:
    db, branch = _branch(tmp_path)

    result = _rollup(CliRunner(), db, [branch["empty"]])

    assert result.exit_code == 0, result.output
    assert "no outcomes yet" in result.output
    assert "0 outcome" not in result.output
    assert "0.00" not in result.output, "a theme nobody has filed anything under has no score"


def test_a_theme_of_unscored_outcomes_names_the_gap_not_a_zero(tmp_path) -> None:
    db, branch = _branch(tmp_path)

    result = _rollup(CliRunner(), db, [branch["unscored"]])

    assert result.exit_code == 0, result.output
    assert "1 outcome(s)" in result.output
    assert "nothing measured yet" in result.output
    assert "0.00" not in result.output


def test_the_json_carries_a_null_top_rather_than_a_zero(tmp_path) -> None:
    db, branch = _branch(tmp_path)

    scored = _json(CliRunner(), ["--db", db, "themes", "rollup", branch["parent"], "--json"])
    assert (scored["theme_id"], scored["name"]) == (branch["parent"], "Cash timing")
    assert (scored["outcomes"], scored["measured"]) == (4, 2)
    assert scored["top_opportunity"] == 17.0

    unscored = _json(CliRunner(), ["--db", db, "themes", "rollup", branch["unscored"], "--json"])
    assert (unscored["outcomes"], unscored["measured"]) == (1, 0)
    assert unscored["top_opportunity"] is None
    assert unscored["top_statement"] is None


def test_a_job_rollup_prints_parents_before_the_themes_under_them(tmp_path) -> None:
    db, branch = _branch(tmp_path)
    order = ["Cash timing", "Payment windows", "Cut-off times", "Bank feeds", "Unreviewed"]

    result = _rollup(CliRunner(), db, ["--job", branch["job_id"]])

    assert result.exit_code == 0, result.output
    positions = {name: result.output.index(name) for name in order}
    assert sorted(order, key=lambda name: positions[name]) == order
    assert "4" in result.output.splitlines()[2], "the parent row carries its branch's count"

    rows = _json(CliRunner(), ["--db", db, "themes", "rollup", "--job", branch["job_id"], "--json"])
    assert [row["name"] for row in rows] == order
    assert [row["outcomes"] for row in rows] == [4, 2, 2, 0, 1]


def test_rollup_wants_a_theme_or_a_scope(tmp_path) -> None:
    db, _, _ = _seed(tmp_path)

    result = _rollup(CliRunner(), db, [])

    assert result.exit_code == 1
    assert "rollup wants a theme" in result.output
    assert "name one with THEME_ID or list a scope with --job" in result.output


def test_an_unknown_theme_in_a_rollup_is_reported_not_raised(tmp_path) -> None:
    db, _, _ = _seed(tmp_path)

    result = _rollup(CliRunner(), db, ["t-ghost"])

    assert result.exit_code == 1
    assert "theme not found: t-ghost" in result.output
    assert "Traceback" not in result.output
