"""Tests for the evidence CLI group."""

from __future__ import annotations

import json

import pytest
from agentic_odi_cli.cli import app
from typer.testing import CliRunner


def _job_id(runner: CliRunner, db: str) -> str:
    result = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Job", "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def _add_evidence(runner: CliRunner, db: str, job_id: str, content: str = "Slow setup") -> str:
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "evidence",
            "add",
            "--source-name",
            "gong",
            "--source-kind",
            "mcp",
            "--name",
            "feedback",
            "--content",
            content,
            "--job-id",
            job_id,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def test_evidence_add_list_get_delete(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    evidence_id = _add_evidence(runner, db, job_id)

    listed = runner.invoke(app, ["--db", db, "evidence", "list", "--job-id", job_id, "--json"])
    payload = json.loads(listed.output)
    assert [item["id"] for item in payload] == [evidence_id]
    assert payload[0]["content"] == "Slow setup"

    fetched = runner.invoke(app, ["--db", db, "evidence", "get", evidence_id, "--json"])
    assert json.loads(fetched.output)["source_name"] == "gong"

    deleted = runner.invoke(app, ["--db", db, "evidence", "delete", evidence_id, "-y"])
    assert deleted.exit_code == 0 and "Deleted evidence" in deleted.output

    empty = runner.invoke(app, ["--db", db, "evidence", "list", "--job-id", job_id, "--json"])
    assert json.loads(empty.output) == []


def test_evidence_add_unknown_job_reports_error(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "--db",
            str(tmp_path / "odi.db"),
            "evidence",
            "add",
            "--source-name",
            "gong",
            "--name",
            "feedback",
            "--content",
            "quote",
            "--job-id",
            "nope",
        ],
    )

    assert result.exit_code == 1
    assert "Job not found: nope" in result.output


def test_evidence_promote_to_job_and_outcome(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    evidence_id = _add_evidence(runner, db, job_id)

    promoted_job = runner.invoke(
        app,
        ["--db", db, "evidence", "promote", evidence_id, "--to", "job"],
    )
    assert promoted_job.exit_code == 0
    assert "Job created" in promoted_job.output

    promoted_outcome = runner.invoke(
        app,
        [
            "--db",
            db,
            "evidence",
            "promote",
            evidence_id,
            "--to",
            "outcome",
            "--job-id",
            job_id,
            "--statement",
            "Minimize the time to set up when onboarding",
            "--importance",
            "8",
            "--satisfaction",
            "4",
        ],
    )
    assert promoted_outcome.exit_code == 0
    assert "Outcome created" in promoted_outcome.output


def _stored_content(runner: CliRunner, db: str, evidence_id: str) -> str:
    result = runner.invoke(app, ["--db", db, "evidence", "get", evidence_id, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["content"]


def _add_from_file(runner: CliRunner, db: str, path: str) -> str:
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "evidence",
            "add",
            "--source-name",
            "Interview 4",
            "--name",
            "quote",
            "--file",
            path,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def test_evidence_add_file_stores_the_file_text(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    source = tmp_path / "quote.md"
    source.write_text("**Setup takes two days** for every new engineer.\n", encoding="utf-8")

    evidence_id = _add_from_file(runner, db, str(source))

    assert _stored_content(runner, db, evidence_id) == (
        "**Setup takes two days** for every new engineer.\n"
    )


def test_evidence_add_inline_content_is_unchanged(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()

    evidence_id = _add_evidence(runner, db, _job_id(runner, db), content="Slow setup")

    assert _stored_content(runner, db, evidence_id) == "Slow setup"


@pytest.mark.parametrize("suffix", [".txt", ".md", ".markdown", ".vtt", ".srt"])
def test_evidence_add_file_accepts_every_supported_text_format(tmp_path, suffix):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    source = tmp_path / f"quote{suffix}"
    source.write_text("Seedlings take four days to germinate.", encoding="utf-8")

    evidence_id = _add_from_file(runner, db, str(source))

    assert _stored_content(runner, db, evidence_id) == "Seedlings take four days to germinate."


def test_evidence_add_file_rejects_a_missing_path(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--db",
            str(tmp_path / "odi.db"),
            "evidence",
            "add",
            "--source-name",
            "Interview 4",
            "--name",
            "quote",
            "--file",
            str(tmp_path / "gone.md"),
        ],
    )

    assert result.exit_code == 1
    assert "No such file" in result.output
    assert "Traceback" not in result.output


def test_evidence_add_file_and_content_are_mutually_exclusive(tmp_path):
    source = tmp_path / "quote.md"
    source.write_text("from the file", encoding="utf-8")
    result = CliRunner().invoke(
        app,
        [
            "--db",
            str(tmp_path / "odi.db"),
            "evidence",
            "add",
            "--source-name",
            "Interview 4",
            "--name",
            "quote",
            "--file",
            str(source),
            "--content",
            "from the shell",
        ],
    )

    assert result.exit_code == 1
    assert "one of --content or --file" in result.output
    assert "Traceback" not in result.output


def test_evidence_add_requires_either_content_or_file(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "--db",
            str(tmp_path / "odi.db"),
            "evidence",
            "add",
            "--source-name",
            "Interview 4",
            "--name",
            "quote",
        ],
    )

    assert result.exit_code == 1
    assert "one of --content or --file" in result.output


def test_evidence_add_dash_reads_stdin(tmp_path):
    db = str(tmp_path / "odi.db")
    result = CliRunner().invoke(
        app,
        [
            "--db",
            db,
            "evidence",
            "add",
            "--source-name",
            "Interview 4",
            "--name",
            "quote",
            "--file",
            "-",
            "--json",
        ],
        input="Piped straight from the terminal.\n",
    )

    assert result.exit_code == 0, result.output
    assert _stored_content(CliRunner(), db, json.loads(result.output)["id"]) == (
        "Piped straight from the terminal.\n"
    )


def test_evidence_add_refuses_pdf_and_points_at_the_studio(tmp_path):
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.4 not a real document")
    result = CliRunner().invoke(
        app,
        [
            "--db",
            str(tmp_path / "odi.db"),
            "evidence",
            "add",
            "--source-name",
            "Interview 4",
            "--name",
            "quote",
            "--file",
            str(source),
        ],
    )

    assert result.exit_code == 1
    assert "not supported from the CLI yet" in result.output
    assert "attach it in the Studio" in result.output
    assert "Traceback" not in result.output


def test_evidence_add_refuses_docx_and_points_at_the_studio(tmp_path):
    source = tmp_path / "notes.docx"
    source.write_bytes(b"PK\x03\x04 not a real document")
    result = CliRunner().invoke(
        app,
        [
            "--db",
            str(tmp_path / "odi.db"),
            "evidence",
            "add",
            "--source-name",
            "Interview 4",
            "--name",
            "quote",
            "--file",
            str(source),
        ],
    )

    assert result.exit_code == 1
    assert "not supported from the CLI yet" in result.output
    assert "Traceback" not in result.output


def test_evidence_add_refuses_an_unknown_extension(tmp_path):
    source = tmp_path / "binary.bin"
    source.write_bytes(b"\x00\x01\x02")
    result = CliRunner().invoke(
        app,
        [
            "--db",
            str(tmp_path / "odi.db"),
            "evidence",
            "add",
            "--source-name",
            "Interview 4",
            "--name",
            "quote",
            "--file",
            str(source),
        ],
    )

    assert result.exit_code == 1
    assert "not a text format the CLI reads" in result.output


def test_evidence_add_truncates_at_the_studio_limit_and_says_so(tmp_path):
    db = str(tmp_path / "odi.db")
    source = tmp_path / "long.md"
    source.write_text("x" * 20_500, encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "--db",
            db,
            "evidence",
            "add",
            "--source-name",
            "Interview 4",
            "--name",
            "quote",
            "--file",
            str(source),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "20000 of 20500 characters" in result.stderr


def test_evidence_add_truncation_notice_keeps_json_stdout_parseable(tmp_path):
    db = str(tmp_path / "odi.db")
    source = tmp_path / "long.md"
    source.write_text("y" * 20_500, encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "--db",
            db,
            "evidence",
            "add",
            "--source-name",
            "Interview 4",
            "--name",
            "quote",
            "--file",
            str(source),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert len(_stored_content(CliRunner(), db, payload["id"])) == 20_000
    assert "20000 of 20500" in result.stderr


def test_evidence_add_without_truncation_prints_no_notice(tmp_path):
    db = str(tmp_path / "odi.db")
    source = tmp_path / "short.md"
    source.write_text("z" * 40, encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "--db",
            db,
            "evidence",
            "add",
            "--source-name",
            "Interview 4",
            "--name",
            "quote",
            "--file",
            str(source),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "characters" not in result.stderr
