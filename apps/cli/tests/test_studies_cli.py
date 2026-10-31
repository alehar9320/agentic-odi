"""Tests for the studies CLI group (M2-05).

The two promises this group makes are that a new wave starts unmeasured and that
an absent score prints as an em dash, never as ``0``. Both are asserted here from
the command line, not from the service.
"""

from __future__ import annotations

import json
from typing import Any

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

STATEMENT = "Minimize the time it takes to harvest the field when the weather turns"
ADDED = "Minimize the cost of the fuel burned while the tractor is idling"


def _json(runner: CliRunner, args: list[str]) -> Any:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _seed(tmp_path) -> tuple[str, str, str]:
    """A job plus wave 1, ready to score."""
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job = _json(
        runner,
        [
            "--db",
            db,
            "jobs",
            "add",
            "--name",
            "Corn growers",
            "--description",
            "Grow corn profitably",
            "--json",
        ],
    )
    job_id = str(job["id"])  # type: ignore[index]
    wave = _json(
        runner,
        [
            "--db",
            db,
            "studies",
            "open",
            "--job",
            job_id,
            "--name",
            "Corn growers, quarterly pulse",
            "--guide-name",
            "Core interview",
            "--question",
            "Walk me through harvest",
            "--statement",
            STATEMENT,
            "--theme",
            "yield",
            "--json",
        ],
    )
    return db, job_id, str(wave["id"])  # type: ignore[index]


def _score(
    runner: CliRunner, db: str, job_id: str, statement: str, wave_id: str, i: float, s: float
):
    return _json(
        runner,
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
            str(i),
            "--satisfaction",
            str(s),
            "--study-id",
            wave_id,
            "--json",
        ],
    )


def test_open_study_starts_wave_one_with_the_frame(tmp_path) -> None:
    db, job_id, wave_id = _seed(tmp_path)
    runner = CliRunner()

    listed = _json(runner, ["--db", db, "studies", "list", "--job", job_id, "--json"])

    assert [item["id"] for item in listed] == [wave_id]  # type: ignore[index]
    assert listed[0]["wave"] == 1  # type: ignore[index]
    assert listed[0]["frame"]["outcome_statements"] == [STATEMENT]  # type: ignore[index]


def test_next_wave_copies_the_frame_with_no_measurement(tmp_path) -> None:
    db, job_id, wave_one = _seed(tmp_path)
    runner = CliRunner()
    _score(runner, db, job_id, STATEMENT, wave_one, 8.0, 4.0)

    wave_two = _json(runner, ["--db", db, "studies", "next", wave_one, "--json"])

    assert wave_two["wave"] == 2  # type: ignore[index]
    assert wave_two["frame"]["outcome_statements"] == [STATEMENT]  # type: ignore[index]
    scored = _json(runner, ["--db", db, "desired-outcomes", "list", "--job-id", job_id, "--json"])
    assert [item["study_id"] for item in scored] == [wave_one]  # type: ignore[index]


def test_compare_renders_an_absent_score_as_an_em_dash(tmp_path) -> None:
    db, job_id, wave_one = _seed(tmp_path)
    runner = CliRunner()
    wave_two = _json(runner, ["--db", db, "studies", "next", wave_one, "--json"])
    wave_two_id = str(wave_two["id"])  # type: ignore[index]
    _score(runner, db, job_id, ADDED, wave_two_id, 6.0, 3.0)

    result = runner.invoke(app, ["--db", db, "studies", "compare", wave_one, wave_two_id])

    assert result.exit_code == 0, result.output
    assert "added" in result.output
    # The new statement's wave-a score is absent, so it prints as an em dash.
    row = next(line for line in result.output.splitlines() if "fuel" in line)
    assert "—" in row
    assert " 0 " not in row


def test_compare_reports_moved_scores(tmp_path) -> None:
    db, job_id, wave_one = _seed(tmp_path)
    runner = CliRunner()
    wave_two = _json(runner, ["--db", db, "studies", "next", wave_one, "--json"])
    wave_two_id = str(wave_two["id"])  # type: ignore[index]
    _score(runner, db, job_id, STATEMENT, wave_one, 4.0, 4.0)
    _score(runner, db, job_id, STATEMENT, wave_two_id, 7.0, 4.0)

    body = _json(runner, ["--db", db, "studies", "compare", wave_one, wave_two_id, "--json"])

    item = next(row for row in body["per_outcome"] if row["statement"] == STATEMENT)  # type: ignore[index]
    assert item["score_a"] == 4.0
    assert item["score_b"] == 7.0
    assert item["delta"] == 3.0
    assert item["status"] == "moved"


def test_compare_refuses_waves_from_different_jobs(tmp_path) -> None:
    db, job_id, wave_one = _seed(tmp_path)
    runner = CliRunner()
    other = _json(
        runner,
        ["--db", db, "jobs", "add", "--name", "Wheat growers", "--json"],
    )
    other_wave = _json(
        runner,
        [
            "--db",
            db,
            "studies",
            "open",
            "--job",
            str(other["id"]),  # type: ignore[index]
            "--name",
            "Wheat pulse",
            "--json",
        ],
    )

    result = runner.invoke(
        app,
        ["--db", db, "studies", "compare", wave_one, str(other_wave["id"])],  # type: ignore[index]
    )

    assert result.exit_code != 0
    assert "study" in result.output.lower()


def test_list_is_empty_before_a_study_is_opened(tmp_path) -> None:
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    result = runner.invoke(app, ["--db", db, "studies", "list"])

    assert result.exit_code == 0, result.output
    assert "No studies yet" in result.output
