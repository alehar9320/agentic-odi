"""Tests for `odi brief export` (C4, ALH-35).

Pinned choices:

* ``--format md`` writes the markdown brief; ``--format html`` wraps the same
  markdown in a standalone document that opens with no app CSS and no network
  asset.
* ``--out`` writes the file and prints its path; without ``--out`` the document
  goes to stdout.
* An unknown format exits nonzero with a message.
* A quote that contains markup is escaped in both formats.
* The HTML carries a snapshot banner naming its source.
"""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _seed(db: str) -> str:
    job = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Publish a plugin", "--json"])
    assert job.exit_code == 0, job.output
    job_id = json.loads(job.output)["id"]
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
            ],
        )
        assert outcome.exit_code == 0, outcome.output
    return job_id


def test_brief_export_writes_a_file_and_prints_its_path(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id = _seed(db)
    target = tmp_path / "brief.md"

    result = runner.invoke(
        app,
        ["--db", db, "brief", "export", "--job-id", job_id, "--out", str(target)],
    )

    assert result.exit_code == 0, result.output
    assert result.output.strip() == str(target)
    assert target.is_file()
    assert "# Brief: Publish a plugin" in target.read_text(encoding="utf-8")


def test_brief_export_to_stdout_renders_the_case(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id = _seed(db)

    result = runner.invoke(app, ["--db", db, "brief", "export", "--job-id", job_id])

    assert result.exit_code == 0, result.output
    assert "## Underserved outcomes" in result.output
    assert "## The decision we are considering" in result.output


def test_brief_export_html_is_standalone(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id = _seed(db)

    result = runner.invoke(
        app, ["--db", db, "brief", "export", "--job-id", job_id, "--format", "html"]
    )

    assert result.exit_code == 0, result.output
    assert result.output.startswith("<!DOCTYPE html>")
    assert "<style>" in result.output
    assert "Exported from the recorded data" in result.output
    assert "http://" not in result.output
    assert "https://" not in result.output


def test_brief_to_html_escapes_hostile_markdown() -> None:
    from agentic_odi_cli.brief import brief_to_html

    document = brief_to_html(
        "# Brief: <script>alert(1)</script>\n\n- Quote: \"<img src=x onerror=alert(1)>\"",
        source="job <b>1</b>",
    )

    assert "<script>alert" not in document
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in document
    assert "&lt;img src=x onerror=alert(1)&gt;" in document
    assert "<b>1</b>" not in document
    assert "job &lt;b&gt;1&lt;/b&gt;" in document


def test_brief_export_missing_job_exits_nonzero(tmp_path) -> None:
    db = str(tmp_path / "studio.db")

    result = runner.invoke(app, ["--db", db, "brief", "export", "--job-id", "JOB-NOPE"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_brief_export_unknown_format_exits_nonzero(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job_id = _seed(db)

    result = runner.invoke(
        app, ["--db", db, "brief", "export", "--job-id", job_id, "--format", "pdf"]
    )

    assert result.exit_code == 1
    assert "unknown format" in result.output.lower()


def test_brief_export_missing_measurement_is_not_zero(tmp_path) -> None:
    db = str(tmp_path / "studio.db")
    job = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Sparse job", "--json"])
    job_id = json.loads(job.output)["id"]

    result = runner.invoke(app, ["--db", db, "brief", "export", "--job-id", job_id])

    assert result.exit_code == 0, result.output
    assert "No measured outcomes yet" in result.output
    assert "- Score: 0" not in result.output
