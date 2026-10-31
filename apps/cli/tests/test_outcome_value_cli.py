"""Tests for `odi desired-outcomes value` (W1/ALH-64).

Readiness choices pinned here:

* The CLI is a thin adapter: it passes the estimate, unit, basis, sample and
  source through to one ``set_outcome_value`` call and never derives a value.
* Omitting ``--estimate`` clears the value; the companions go with it.
* A ``market`` or ``pilot`` basis without ``--source`` exits nonzero with the
  service's own sentence and no traceback.
* A missing unit on a real estimate is refused.
* The score is untouched by valuing an outcome.
"""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _seed(db: str) -> tuple[str, str]:
    job = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Publish a plugin", "--json"])
    assert job.exit_code == 0, job.output
    job_id = json.loads(job.output)["id"]
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
            "Minimize the time it takes to publish a plugin when a release is ready",
            "--importance",
            "9",
            "--satisfaction",
            "3",
            "--json",
        ],
    )
    assert outcome.exit_code == 0, outcome.output
    return job_id, json.loads(outcome.output)["id"]


def test_value_records_the_estimate_and_its_basis(tmp_path):
    db = str(tmp_path / "odi.db")
    _, outcome_id = _seed(db)
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "desired-outcomes",
            "value",
            outcome_id,
            "--estimate",
            "250000",
            "--unit",
            "currency",
            "--basis",
            "market",
            "--source",
            "Gartner 2025 plugin market report",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["value_estimate"] == 250000.0
    assert payload["value_unit"] == "currency"
    assert payload["value_basis"] == "market"
    assert payload["value_source"] == "Gartner 2025 plugin market report"


def test_value_never_derives_from_the_score(tmp_path):
    db = str(tmp_path / "odi.db")
    _, outcome_id = _seed(db)
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "desired-outcomes",
            "value",
            outcome_id,
            "--estimate",
            "7",
            "--unit",
            "users",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["value_estimate"] == 7.0
    # The score stays what importance/satisfaction produced.
    assert payload["opportunity_score"] == 15.0


def test_omitting_the_estimate_clears_the_value(tmp_path):
    db = str(tmp_path / "odi.db")
    _, outcome_id = _seed(db)
    runner.invoke(
        app,
        [
            "--db",
            db,
            "desired-outcomes",
            "value",
            outcome_id,
            "--estimate",
            "100",
            "--unit",
            "users",
            "--json",
        ],
    )
    cleared = runner.invoke(app, ["--db", db, "desired-outcomes", "value", outcome_id, "--json"])
    assert cleared.exit_code == 0, cleared.output
    payload = json.loads(cleared.output)
    assert payload["value_estimate"] is None
    assert payload["value_unit"] is None


def test_a_market_basis_without_a_source_exits_nonzero(tmp_path):
    db = str(tmp_path / "odi.db")
    _, outcome_id = _seed(db)
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "desired-outcomes",
            "value",
            outcome_id,
            "--estimate",
            "100",
            "--unit",
            "currency",
            "--basis",
            "market",
        ],
    )
    assert result.exit_code != 0
    assert "value_source" in result.output
    assert "Traceback" not in result.output


def test_an_estimate_without_a_unit_exits_nonzero(tmp_path):
    db = str(tmp_path / "odi.db")
    _, outcome_id = _seed(db)
    result = runner.invoke(
        app,
        ["--db", db, "desired-outcomes", "value", outcome_id, "--estimate", "100"],
    )
    assert result.exit_code != 0
    assert "unit" in result.output
    assert "Traceback" not in result.output


def test_an_unknown_outcome_exits_nonzero(tmp_path):
    db = str(tmp_path / "odi.db")
    _seed(db)
    result = runner.invoke(
        app,
        ["--db", db, "desired-outcomes", "value", "nope", "--estimate", "1", "--unit", "users"],
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output
