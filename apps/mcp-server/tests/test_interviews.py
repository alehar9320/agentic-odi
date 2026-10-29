"""MCP coverage for transcript import and the interview quote tools (A2)."""

from __future__ import annotations

import json

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client
from mcp.types import TextContent

VTT = """WEBVTT

00:00:01.000 --> 00:00:03.000
<v Ana>Setup takes forever.

00:00:03.000 --> 00:00:05.500
<v Bo>Worse for new hires.
"""


def _text(result) -> str:
    content = result.content[0]
    assert isinstance(content, TextContent)
    return content.text


@pytest.mark.asyncio
async def test_import_transcript_creates_interview_and_quotes() -> None:
    async with Client(mcp) as client:
        await client.call_tool("add_job", {"name": "Onboard"})
        jobs = json.loads(_text(await client.call_tool("get_jobs", {})))
        job_id = jobs[0]["id"]

        result = await client.call_tool(
            "import_transcript",
            {
                "text": VTT,
                "title": "Ana — onboarding",
                "participant_label": "Ana",
                "job_id": job_id,
            },
        )
        payload = json.loads(_text(result))
        interview_id = payload["interview"]["id"]

        quotes = json.loads(
            _text(await client.call_tool("list_quotes", {"interview_id": interview_id}))
        )

    assert payload["quote_count"] == 2
    assert payload["interview"]["job_id"] == job_id
    assert [q["text"] for q in quotes] == ["Setup takes forever.", "Worse for new hires."]
    assert [q["speaker"] for q in quotes] == ["Ana", "Bo"]
    assert [q["ordinal"] for q in quotes] == [0, 1]


@pytest.mark.asyncio
async def test_import_transcript_reports_malformed_input() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "import_transcript",
            {
                "text": "WEBVTT\n\n00:00:1.0 --> nope\nhello\n",
                "title": "T",
                "participant_label": "P",
            },
        )

    assert _text(result).startswith("Error: ")
    assert "cue timing" in _text(result)


@pytest.mark.asyncio
async def test_import_transcript_reports_unknown_job() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "import_transcript",
            {
                "text": VTT,
                "title": "T",
                "participant_label": "P",
                "job_id": "missing",
            },
        )

    assert _text(result) == "Job not found: missing"


@pytest.mark.asyncio
async def test_import_transcript_explicit_format_overrides_extension() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "import_transcript",
            {
                "text": VTT,
                "title": "T",
                "participant_label": "P",
                "filename": "mislabeled.txt",
                "format": "vtt",
            },
        )

    assert json.loads(_text(result))["quote_count"] == 2
