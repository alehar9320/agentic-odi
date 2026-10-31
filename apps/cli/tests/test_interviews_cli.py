"""Tests for the interviews CLI group (A1)."""

from __future__ import annotations

import json

import pytest
from agentic_odi_cli.cli import app
from typer.testing import CliRunner


def _job_id(runner: CliRunner, db: str) -> str:
    result = runner.invoke(app, ["--db", db, "jobs", "add", "--name", "Job", "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def _interview_id(runner: CliRunner, db: str, job_id: str) -> str:
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "add",
            "--title",
            "Ana — onboarding",
            "--participant",
            "Ana",
            "--role",
            "Ops lead",
            "--job-id",
            job_id,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["id"]


def test_interview_add_list_get_delete(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    interview_id = _interview_id(runner, db, job_id)

    listed = runner.invoke(app, ["--db", db, "interviews", "list", "--job-id", job_id, "--json"])
    payload = json.loads(listed.output)
    assert [item["id"] for item in payload] == [interview_id]
    assert payload[0]["participant_label"] == "Ana"

    fetched = runner.invoke(app, ["--db", db, "interviews", "get", interview_id, "--json"])
    assert json.loads(fetched.output)["title"] == "Ana — onboarding"

    deleted = runner.invoke(app, ["--db", db, "interviews", "delete", interview_id, "-y"])
    assert deleted.exit_code == 0 and "Deleted interview" in deleted.output

    empty = runner.invoke(app, ["--db", db, "interviews", "list", "--job-id", job_id, "--json"])
    assert json.loads(empty.output) == []


def test_quotes_command_shows_ordinal_order(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    interview_id = _interview_id(runner, db, job_id)

    # Quotes are added through the local backend tool surface.
    from agentic_odi_cli.backend import LocalBackend

    backend = LocalBackend(db_path=db)
    backend.call("add_quote", {"interview_id": interview_id, "text": "first"})
    backend.call("add_quote", {"interview_id": interview_id, "text": "second"})

    quotes = runner.invoke(app, ["--db", db, "interviews", "quotes", interview_id, "--json"])
    payload = json.loads(quotes.output)
    assert [q["text"] for q in payload] == ["first", "second"]
    assert [q["ordinal"] for q in payload] == [0, 1]


def test_get_missing_interview_reports_not_found(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    result = runner.invoke(app, ["--db", db, "interviews", "get", "missing"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


VTT = """WEBVTT

00:00:01.000 --> 00:00:03.000
<v Ana>Setup takes forever.

00:00:03.000 --> 00:00:05.500
<v Bo>Worse for new hires.
"""

SRT = """1
00:00:01,000 --> 00:00:03,000
Setup takes forever.

2
00:00:03,000 --> 00:00:05,500
Worse for new hires.
"""

MARKDOWN = """**Ana:** Setup takes forever.
It is the worst part of onboarding.

**Bo:** Agreed.
"""

PLAIN = """Setup takes forever for every new engineer.

It is worse for people joining remotely.
"""


def _write(tmp_path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_import_creates_interview_and_ordered_quotes(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = _job_id(runner, db)
    path = _write(tmp_path, "session.vtt", VTT)

    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "import",
            path,
            "--title",
            "Ana — onboarding",
            "--participant",
            "Ana",
            "--job-id",
            job_id,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    interview_id = payload["interview"]["id"]
    assert payload["quote_count"] == 2
    assert payload["interview"]["job_id"] == job_id

    quotes = runner.invoke(app, ["--db", db, "interviews", "quotes", interview_id, "--json"])
    rows = json.loads(quotes.output)
    assert [q["text"] for q in rows] == ["Setup takes forever.", "Worse for new hires."]
    assert [q["speaker"] for q in rows] == ["Ana", "Bo"]
    assert [q["ordinal"] for q in rows] == [0, 1]
    # A VTT import keeps the cue timing, not just the speaker.
    assert [q["start_ms"] for q in rows] == [1000, 3000]
    assert [q["end_ms"] for q in rows] == [3000, 5500]


def test_import_from_stdin(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "import",
            "-",
            "--title",
            "Notes",
            "--participant",
            "P1",
            "--json",
        ],
        input="Setup is slow.\n\nRemote is worse.\n",
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["quote_count"] == 2
    assert payload["interview"]["job_id"] is None


def test_import_explicit_format_overrides_extension(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    # A .txt file that is actually VTT must parse as VTT when told to.
    path = _write(tmp_path, "mislabeled.txt", VTT)
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "import",
            path,
            "--title",
            "T",
            "--participant",
            "P",
            "--format",
            "vtt",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["quote_count"] == 2


def test_import_malformed_transcript_writes_nothing(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    path = _write(tmp_path, "bad.vtt", "WEBVTT\n\n00:00:1.0 --> nope\nhello\n")

    result = runner.invoke(
        app,
        ["--db", db, "interviews", "import", path, "--title", "T", "--participant", "P"],
    )
    assert result.exit_code != 0
    assert "cue timing" in result.output

    # The parse ran before any write: no interview and no quotes exist.
    listed = runner.invoke(app, ["--db", db, "interviews", "list", "--json"])
    assert json.loads(listed.output) == []


def test_import_missing_file_reports_error(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "import",
            str(tmp_path / "nope.vtt"),
            "--title",
            "T",
            "--participant",
            "P",
        ],
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_import_unknown_job_reports_not_found(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    path = _write(tmp_path, "session.vtt", VTT)
    result = runner.invoke(
        app,
        [
            "--db",
            db,
            "interviews",
            "import",
            path,
            "--title",
            "T",
            "--participant",
            "P",
            "--job-id",
            "missing",
        ],
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


@pytest.mark.parametrize(
    ("name", "text", "expected_speakers", "expected_texts"),
    [
        ("session.vtt", VTT, ["Ana", "Bo"], ["Setup takes forever.", "Worse for new hires."]),
        ("session.srt", SRT, [None, None], ["Setup takes forever.", "Worse for new hires."]),
        (
            "notes.md",
            MARKDOWN,
            ["Ana", "Bo"],
            ["Setup takes forever. It is the worst part of onboarding.", "Agreed."],
        ),
        (
            "plain.txt",
            PLAIN,
            [None, None],
            [
                "Setup takes forever for every new engineer.",
                "It is worse for people joining remotely.",
            ],
        ),
    ],
)
def test_import_covers_all_four_formats(tmp_path, name, text, expected_speakers, expected_texts):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    path = _write(tmp_path, name, text)

    result = runner.invoke(
        app,
        ["--db", db, "interviews", "import", path, "--title", "T", "--participant", "P", "--json"],
    )
    assert result.exit_code == 0, result.output
    interview_id = json.loads(result.output)["interview"]["id"]

    quotes = runner.invoke(app, ["--db", db, "interviews", "quotes", interview_id, "--json"])
    rows = json.loads(quotes.output)
    assert [q["speaker"] for q in rows] == expected_speakers
    assert [q["text"] for q in rows] == expected_texts


def test_import_empty_file_is_refused_with_the_filename(tmp_path):
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    path = _write(tmp_path, "empty.txt", "")

    result = runner.invoke(
        app,
        ["--db", db, "interviews", "import", path, "--title", "T", "--participant", "P"],
    )
    assert result.exit_code != 0
    assert "empty.txt" in result.output
    assert "no transcript content" in result.output.lower()

    # The refusal ran before any write: no interview was created.
    listed = runner.invoke(app, ["--db", db, "interviews", "list", "--json"])
    assert json.loads(listed.output) == []
