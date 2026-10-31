"""``odi demo load`` puts the study in the local store, on purpose and twice-safe.

The loader is the only way a stranger's canvas gets filled before they have
research of their own, so the two properties that make it safe to run — every
row labeled ``origin="demo"``, and a second load that changes nothing — have to
hold through the CLI, not just through the core function.
"""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from agentic_odi_core.demo import DEMO_JOB_ID, FIXTURE_COUNTS
from agentic_odi_core.sqlite_repository import SQLiteRepository
from typer.testing import CliRunner

runner = CliRunner()


def _counts(db: str) -> dict[str, int]:
    repo = SQLiteRepository(db_path=db)
    try:
        return {
            "jobs": len(repo.jobs),
            "steps": len(repo.steps),
            "outcomes": len(repo.outcomes),
            "evidence": len(repo.evidence),
        }
    finally:
        repo.close()


def test_demo_load_fills_an_empty_store(tmp_path) -> None:
    db = str(tmp_path / "demo.db")

    result = runner.invoke(app, ["--db", db, "demo", "load"])

    assert result.exit_code == 0, result.output
    assert _counts(db) == FIXTURE_COUNTS


def test_every_loaded_row_is_labeled_a_demo(tmp_path) -> None:
    db = str(tmp_path / "demo.db")
    _demo_load(db)

    repo = SQLiteRepository(db_path=db)
    try:
        labeled = [
            *[job.origin for job in repo.jobs.values()],
            *[step.origin for step in repo.steps.values()],
            *[outcome.origin for outcome in repo.outcomes.values()],
            *[evidence.origin for evidence in repo.evidence.values()],
        ]
        assert labeled, "the load wrote nothing"
        assert set(labeled) == {"demo"}
    finally:
        repo.close()


def test_demo_load_twice_changes_nothing(tmp_path) -> None:
    db = str(tmp_path / "demo.db")

    _demo_load(db)
    second = runner.invoke(app, ["--db", db, "demo", "load"])

    assert second.exit_code == 0, second.output
    assert _counts(db) == FIXTURE_COUNTS


def _add_job(db: str, name: str) -> str:
    result = runner.invoke(
        app,
        ["--db", db, "jobs", "add", "--name", name, "--json"],
    )
    assert result.exit_code == 0, result.output
    return str(json.loads(result.output)["id"])


def _demo_load(db: str, *extra: str) -> object:
    result = runner.invoke(app, ["--db", db, "demo", "load", *extra])
    assert result.exit_code == 0, result.output
    return result


def test_demo_load_reports_the_job_it_filled(tmp_path) -> None:
    db = str(tmp_path / "demo.db")

    result = runner.invoke(app, ["--db", db, "demo", "load", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["job_id"] == DEMO_JOB_ID
    assert payload["counts"] == FIXTURE_COUNTS


def test_demo_load_onto_an_existing_job_uses_it(tmp_path) -> None:
    db = str(tmp_path / "demo.db")
    job_id = _add_job(db, "Reconcile supplier invoices")

    result = runner.invoke(app, ["--db", db, "demo", "load", "--job", job_id, "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["job_id"] == job_id
    repo = SQLiteRepository(db_path=db)
    try:
        assert repo.get_job(DEMO_JOB_ID) is None
        target = repo.get_job(job_id)
        assert target is not None
        assert target.name == "Reconcile supplier invoices"
        assert len(repo.outcomes) == FIXTURE_COUNTS["outcomes"]
        assert all(outcome.job_id == job_id for outcome in repo.outcomes.values())
    finally:
        repo.close()


def test_demo_load_onto_a_missing_job_is_refused(tmp_path) -> None:
    db = str(tmp_path / "demo.db")

    result = runner.invoke(app, ["--db", db, "demo", "load", "--job", "nope"])

    assert result.exit_code == 1
    assert "nope" in result.output


def test_demo_load_needs_a_local_store(tmp_path) -> None:
    db = str(tmp_path / "demo.db")

    result = runner.invoke(app, ["--db", db, "--backend", "mcp", "demo", "load"])

    assert result.exit_code == 1
    assert "local" in result.output


def test_demo_load_leaves_real_research_alone(tmp_path) -> None:
    db = str(tmp_path / "demo.db")
    job_id = _add_job(db, "Reconcile supplier invoices")
    outcome_result = runner.invoke(
        app,
        [
            "--db",
            db,
            "desired-outcomes",
            "add",
            "--job-id",
            job_id,
            "--statement",
            "Minimize the time it takes to match an invoice when it arrives",
            "--importance",
            "8",
            "--satisfaction",
            "3",
        ],
    )
    assert outcome_result.exit_code == 0, outcome_result.output

    _demo_load(db)

    repo = SQLiteRepository(db_path=db)
    try:
        target = repo.get_job(job_id)
        assert target is not None
        assert target.name == "Reconcile supplier invoices"
        own = [outcome for outcome in repo.outcomes.values() if outcome.job_id == job_id]
        assert len(own) == 1
        assert own[0].origin == "user"
    finally:
        repo.close()
