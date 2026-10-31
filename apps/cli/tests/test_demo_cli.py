"""Tests for ``odi demo`` — the labelled sample workspace.

The demo is deliberately additive and every row it writes carries
``origin="demo"``, so these tests pin both properties: a second load is a
no-op, and ``demo clear`` removes only the demo rows.
"""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner


def test_load_fills_a_store_and_reports_the_counts(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    result = runner.invoke(app, ["--db", db, "demo", "load"])

    assert result.exit_code == 0, result.output
    assert 'origin="demo"' in result.stdout
    assert "40 outcomes" in result.stdout


def test_load_json_is_the_machine_shape(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    result = runner.invoke(app, ["--db", db, "demo", "load", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["origin"] == "demo"
    assert payload["jobs"] == 1
    assert payload["outcomes"] == 40


def test_a_second_load_is_a_no_op(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    first = runner.invoke(app, ["--db", db, "demo", "load", "--json"])
    assert first.exit_code == 0, first.output
    first_job = json.loads(first.stdout)["job_id"]

    second = runner.invoke(app, ["--db", db, "demo", "load", "--json"])
    assert second.exit_code == 0, second.output
    payload = json.loads(second.stdout)
    assert payload["job_id"] == first_job
    assert payload["outcomes"] == 40

    jobs = runner.invoke(app, ["--db", db, "jobs", "list", "--json"])
    assert jobs.exit_code == 0
    assert len(json.loads(jobs.stdout)) == 1


def test_clear_removes_only_demo_rows(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    loaded = runner.invoke(app, ["--db", db, "demo", "load", "--json"])
    assert loaded.exit_code == 0, loaded.output

    own = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "My own research", "--json"])
    assert own.exit_code == 0, own.output
    own_job = json.loads(own.stdout)["id"]

    cleared = runner.invoke(app, ["--db", db, "demo", "clear", "--yes"])
    assert cleared.exit_code == 0, cleared.output
    assert "left untouched" in cleared.stdout

    jobs = runner.invoke(app, ["--db", db, "jobs", "list", "--json"])
    assert jobs.exit_code == 0
    remaining = json.loads(jobs.stdout)
    assert [job["id"] for job in remaining] == [own_job]


def test_clear_aborts_without_confirmation(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    loaded = runner.invoke(app, ["--db", db, "demo", "load", "--json"])
    assert loaded.exit_code == 0, loaded.output

    aborted = runner.invoke(app, ["--db", db, "demo", "clear"], input="n\n")
    assert aborted.exit_code != 0

    jobs = runner.invoke(app, ["--db", db, "jobs", "list", "--json"])
    assert jobs.exit_code == 0
    assert len(json.loads(jobs.stdout)) == 1
