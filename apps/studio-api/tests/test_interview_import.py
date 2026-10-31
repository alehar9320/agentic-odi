"""Router tests for importing a transcript from the thread (A2.2 / ALH-152).

``POST /api/interviews/import`` takes the composer's attachment text plus
metadata and hands it to the same shared importer ``odi interviews import``
calls — the browser never re-sniffs the format. A success returns the created
interview and its quote count; a refusal names the file and the parser's reason
and leaves no partial interview behind.
"""

from __future__ import annotations

import json

from agentic_odi_cli.cli import app as cli_app
from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient
from typer.testing import CliRunner

MARKDOWN = "**Ana:** Onboarding takes forever.\n\n**Ana:** I gave up on the setup wizard."
VTT = (
    "WEBVTT\n\n"
    "00:00:01.000 --> 00:00:03.000\n<v Ana>Onboarding takes forever.\n\n"
    "00:00:04.000 --> 00:00:06.000\n<v Bo>I gave up on the setup wizard.\n"
)


def _client() -> tuple[TestClient, ODIService]:
    repo = InMemoryRepository()
    service = ODIService(repo)
    client = TestClient(create_app(repo, backend="local"))
    return client, service


def test_import_returns_the_interview_and_its_quote_count() -> None:
    client, service = _client()

    response = client.post(
        "/api/interviews/import",
        json={
            "text": MARKDOWN,
            "title": "Ana onboarding",
            "participant": "Ana",
            "filename": "ana.md",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["quote_count"] == 2
    interview_id = body["interview"]["id"]
    stored = service.get_interview(interview_id)
    assert stored is not None
    assert stored.title == "Ana onboarding"
    quotes = service.list_quotes(interview_id)
    assert [quote.text for quote in quotes] == [
        "Onboarding takes forever.",
        "I gave up on the setup wizard.",
    ]
    assert [quote.speaker for quote in quotes] == ["Ana", "Ana"]


def test_import_uses_the_filename_to_pick_the_format() -> None:
    client, service = _client()

    response = client.post(
        "/api/interviews/import",
        json={
            "text": VTT,
            "title": "Ana and Bo",
            "participant": "Ana",
            "filename": "session.vtt",
        },
    )

    assert response.status_code == 200, response.text
    interview_id = response.json()["interview"]["id"]
    quotes = service.list_quotes(interview_id)
    assert [quote.speaker for quote in quotes] == ["Ana", "Bo"]
    assert quotes[0].start_ms == 1000
    assert quotes[1].end_ms == 6000


def test_import_accepts_an_explicit_format_for_an_extensionless_file() -> None:
    client, service = _client()

    response = client.post(
        "/api/interviews/import",
        json={
            "text": MARKDOWN,
            "title": "Pasted transcript",
            "participant": "Ana",
            "filename": "pasted",
            "format": "md",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["quote_count"] == 2


def test_import_rejects_a_malformed_transcript_and_writes_nothing() -> None:
    client, service = _client()

    response = client.post(
        "/api/interviews/import",
        json={
            "text": "WEBVTT\n\n00:00:01.000 --> 00:00\n<v Ana>Hi\n",
            "title": "Broken",
            "participant": "Ana",
            "filename": "broken.vtt",
        },
    )

    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "validation"
    assert "broken.vtt" in error["message"]
    assert "malformed cue timing" in error["message"]
    # The refusal left no interview and no quotes behind.
    assert service.list_interviews() == []


def test_import_refuses_an_empty_transcript_by_name() -> None:
    client, service = _client()

    response = client.post(
        "/api/interviews/import",
        json={
            "text": "   \n\n  ",
            "title": "Empty",
            "participant": "Ana",
            "filename": "empty.md",
        },
    )

    assert response.status_code == 422, response.text
    assert "empty.md" in response.json()["error"]["message"]
    assert service.list_interviews() == []


def test_import_reports_an_unknown_job_as_not_found() -> None:
    client, _service = _client()

    response = client.post(
        "/api/interviews/import",
        json={
            "text": MARKDOWN,
            "title": "Ana onboarding",
            "participant": "Ana",
            "filename": "ana.md",
            "job_id": "JOB-does-not-exist",
        },
    )

    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "not_found"


def _quote_shape(quotes) -> list[tuple]:
    """The comparable shape of a quote: text, speaker, and the times it covers."""
    return [(q["text"], q["speaker"], q["start_ms"], q["end_ms"]) for q in quotes]


def test_cli_and_http_import_yield_the_same_ordered_quotes(tmp_path) -> None:
    """The thread's route and ``odi interviews import`` are one importer.

    Both go through :meth:`ODIService.import_transcript`, so the same WebVTT
    must land as the same ordered quote text, speakers, and times whichever
    surface asked for it. This is the A2.2 parity check.
    """
    client, service = _client()
    http_response = client.post(
        "/api/interviews/import",
        json={"text": VTT, "title": "Ana and Bo", "participant": "Ana", "filename": "session.vtt"},
    )
    assert http_response.status_code == 200, http_response.text
    http_quotes = [
        quote.model_dump() for quote in service.list_quotes(http_response.json()["interview"]["id"])
    ]

    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    transcript = tmp_path / "session.vtt"
    transcript.write_text(VTT, encoding="utf-8")
    cli_result = runner.invoke(
        cli_app,
        [
            "--db",
            db,
            "interviews",
            "import",
            str(transcript),
            "--title",
            "Ana and Bo",
            "--participant",
            "Ana",
            "--json",
        ],
    )
    assert cli_result.exit_code == 0, cli_result.output
    cli_interview_id = json.loads(cli_result.output)["interview"]["id"]
    cli_quotes = json.loads(
        runner.invoke(
            cli_app, ["--db", db, "interviews", "quotes", cli_interview_id, "--json"]
        ).output
    )

    expected = [
        ("Onboarding takes forever.", "Ana", 1000, 3000),
        ("I gave up on the setup wizard.", "Bo", 4000, 6000),
    ]
    assert _quote_shape(http_quotes) == expected
    assert _quote_shape(cli_quotes) == expected
