"""`data-export` writes a restorable snapshot of the local store."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agentic_odi_cli.cli import app
from agentic_odi_core import ODIService
from agentic_odi_core.models import Evidence, Job, Outcome
from agentic_odi_core.sqlite_repository import SQLiteRepository
from typer.testing import CliRunner

DEFAULT_NAME = re.compile(r"^odi-export-\d{8}T\d{6}Z\.json$")
runner = CliRunner()


def _seed(db_path: Path, job_name: str = "Ship onboarding") -> str:
    service = ODIService(SQLiteRepository(db_path=str(db_path)))
    job = service.add_job(name=job_name)
    service.add_outcome(
        job.id, "Minimize the time it takes to ship, when onboarding a new customer", 8, 4
    )
    service.add_evidence(
        source_name="gong",
        source_kind="mcp",
        name="Quote",
        content="Onboarding takes two weeks",
        job_id=job.id,
    )
    return job.id


def test_data_export_writes_a_timestamped_file_by_default(tmp_path, monkeypatch):
    db_path = tmp_path / "odi.db"
    monkeypatch.setenv("AGENTIC_ODI_DB", str(db_path))
    monkeypatch.chdir(tmp_path)
    job_id = _seed(db_path)

    result = runner.invoke(app, ["data-export"])

    assert result.exit_code == 0, result.output
    files = list(tmp_path.glob("odi-export-*.json"))
    assert len(files) == 1
    assert DEFAULT_NAME.match(files[0].name)

    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["format"] == "agentic-odi-export"
    assert payload["version"] == 1
    assert payload["job_id"] is None
    assert [job["id"] for job in payload["jobs"]] == [job_id]
    assert len(payload["outcomes"]) == 1
    assert len(payload["evidence"]) == 1


def test_data_export_can_narrow_to_one_job(tmp_path, monkeypatch):
    db_path = tmp_path / "odi.db"
    monkeypatch.setenv("AGENTIC_ODI_DB", str(db_path))
    job_id = _seed(db_path, "First")
    _seed(db_path, "Second")
    output = tmp_path / "out" / "export.json"

    result = runner.invoke(app, ["data-export", "--job-id", job_id, "--output", str(output)])

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["job_id"] == job_id
    assert [job["id"] for job in payload["jobs"]] == [job_id]
    assert {outcome["job_id"] for outcome in payload["outcomes"]} == {job_id}
    assert {item["job_id"] for item in payload["evidence"]} == {job_id}


def test_data_export_round_trips_through_model_validate(tmp_path, monkeypatch):
    db_path = tmp_path / "odi.db"
    monkeypatch.setenv("AGENTIC_ODI_DB", str(db_path))
    _seed(db_path)
    output = tmp_path / "export.json"

    result = runner.invoke(app, ["data-export", "--output", str(output)])

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    jobs = [Job.model_validate(item) for item in payload["jobs"]]
    outcomes = [Outcome.model_validate(item) for item in payload["outcomes"]]
    evidence = [Evidence.model_validate(item) for item in payload["evidence"]]
    assert jobs[0].name == "Ship onboarding"
    assert outcomes[0].job_id == jobs[0].id
    assert evidence[0].job_id == jobs[0].id


def test_data_export_reports_an_unknown_job(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))

    result = runner.invoke(app, ["data-export", "--job-id", "missing"])

    assert result.exit_code == 1
    assert "missing" in result.output
