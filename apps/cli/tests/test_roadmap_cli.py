"""Tests for `odi roadmap show` (C7.2, ALH-160).

Pinned choices:

* The CLI renders the same bytes as the shared ``render_roadmap``; it does not
  regroup or recompute a quarter.
* ``--today`` pins the window so the output is reproducible.
* A baseline nobody measured prints ``not measured``, never ``0``.
* The excluded count and its reason always print.
* An unknown job exits nonzero with a message and no traceback.
* ``--json`` emits the derivation as machine-readable JSON.
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


def _decide(db: str, job_id: str, outcome_id: str, decided_at: str) -> None:
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
            outcome_id,
            "--rationale",
            "The publishing path blocks every release.",
            "--decided-by",
            "dana",
            "--decided-at",
            decided_at,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output


def test_roadmap_show_renders_entries_and_the_exclusion_note(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    _decide(db, job_id, ids[0], "2026-10-01T00:00:00Z")

    result = runner.invoke(
        app,
        ["--db", db, "roadmap", "show", "--job-id", job_id, "--today", "2026-11-15"],
    )

    assert result.exit_code == 0, result.output
    assert "# Outcome roadmap" in result.output
    assert "## 2026-Q4" in result.output
    assert "Minimize the time it takes to publish a plugin" in result.output
    assert "Baseline: not measured" in result.output
    assert "1 outcome(s) have no decision" in result.output


def test_roadmap_show_renders_the_empty_state(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, _ = _seed(db)

    result = runner.invoke(
        app,
        ["--db", db, "roadmap", "show", "--job-id", job_id, "--today", "2026-11-15"],
    )

    assert result.exit_code == 0, result.output
    assert "_No decisions yet._" in result.output


def test_roadmap_show_json_emits_the_derivation(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, ids = _seed(db)
    _decide(db, job_id, ids[0], "2026-10-01T00:00:00Z")

    result = runner.invoke(
        app,
        ["--db", db, "roadmap", "show", "--job-id", job_id, "--today", "2026-11-15", "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["entries"][0]["period"] == "2026-Q4"
    assert payload["entries"][0]["baseline"] is None
    assert payload["undecided_count"] == 1


def test_roadmap_show_missing_job_exits_nonzero_without_a_traceback(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    result = runner.invoke(
        app, ["--db", db, "roadmap", "show", "--job-id", "JOB-NOPE", "--today", "2026-11-15"]
    )

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "JOB-NOPE" in result.output


def test_roadmap_show_refuses_a_non_positive_horizon(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id, _ = _seed(db)

    result = runner.invoke(
        app,
        ["--db", db, "roadmap", "show", "--job-id", job_id, "--horizon", "0"],
    )

    assert result.exit_code != 0
    assert "horizon" in result.output.lower()
