"""Tests for the studies CLI group (ALH-69, M2-05).

A study is one named pass over a job; running it again opens a later wave. These
prove the terminal can open a study, list what exists, refuse a repeated wave and
an unknown job, and reach both through the ``run_tool`` backend seam like every
other command — never by touching the service directly.
"""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner


def _json(runner: CliRunner, args: list[str]) -> object:
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _seed_job(tmp_path) -> tuple[str, str]:
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job = _json(
        runner,
        ["--db", db, "jobs", "add", "--name", "Reconcile invoices", "--json"],
    )
    return db, str(job["id"])  # type: ignore[index]


def test_studies_list_is_empty_until_one_is_open(tmp_path):
    db, job_id = _seed_job(tmp_path)
    runner = CliRunner()

    listed = runner.invoke(app, ["--db", db, "studies", "list", "--job", job_id])
    assert listed.exit_code == 0, listed.output
    assert "No studies yet" in listed.output
    assert "odi studies open" in listed.output


def test_studies_open_creates_a_planned_wave_and_lists_it(tmp_path):
    db, job_id = _seed_job(tmp_path)
    runner = CliRunner()

    opened = _json(
        runner,
        [
            "--db",
            db,
            "studies",
            "open",
            "--job",
            job_id,
            "--name",
            "Q3 sweep",
            "--wave",
            "1",
            "--json",
        ],
    )
    assert opened["status"] == "planned"  # type: ignore[index]
    assert opened["wave"] == 1  # type: ignore[index]
    assert opened["job_id"] == job_id  # type: ignore[index]

    listed = _json(runner, ["--db", db, "studies", "list", "--job", job_id, "--json"])
    assert isinstance(listed, list) and len(listed) == 1
    assert listed[0]["id"] == opened["id"]  # type: ignore[index]

    human = runner.invoke(app, ["--db", db, "studies", "list", "--job", job_id])
    assert "Q3 sweep" in human.output


def test_studies_open_refuses_a_repeated_wave_for_the_same_name(tmp_path):
    db, job_id = _seed_job(tmp_path)
    runner = CliRunner()
    base = ["--db", db, "studies", "open", "--job", job_id, "--name", "Q3 sweep", "--wave", "1"]
    runner.invoke(app, base + ["--json"])

    again = runner.invoke(app, base + ["--json"])
    assert again.exit_code != 0
    assert "already has wave 1" in again.output


def test_studies_open_refuses_an_unknown_job(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    _json(runner, ["--db", db, "jobs", "add", "--name", "A job", "--json"])

    missing = runner.invoke(
        app,
        ["--db", db, "studies", "open", "--job", "not-a-job", "--name", "Q3", "--wave", "1"],
    )
    assert missing.exit_code == 1
    assert "Job not found" in missing.output


def test_studies_resolve_through_the_backend_seam(monkeypatch):
    from agentic_odi_cli import backend as backend_module

    calls: list[tuple[str, dict]] = []
    study = {
        "id": "st-1",
        "job_id": "job-1",
        "name": "Q3 sweep",
        "wave": 1,
        "status": "planned",
        "opened_at": "2026-01-01T00:00:00+00:00",
        "closed_at": None,
        "method_notes": None,
    }

    class _FakeBackend(backend_module.Backend):
        def call(self, tool_name: str, args: dict) -> object:
            calls.append((tool_name, args))
            if tool_name == "open_study":
                return study
            return [study]

    monkeypatch.setattr(backend_module, "require_backend", lambda: _FakeBackend())

    runner = CliRunner()
    assert (
        runner.invoke(
            app, ["studies", "open", "--job", "job-1", "--name", "Q3 sweep", "--wave", "1"]
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["studies", "list", "--job", "job-1"]).exit_code == 0

    assert [name for name, _ in calls] == ["open_study", "list_studies"]
