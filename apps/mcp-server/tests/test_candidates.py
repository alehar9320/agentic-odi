"""MCP coverage for the candidate extraction tools (A4)."""

from __future__ import annotations

import json

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client
from mcp.types import TextContent

QUOTE = "Setup takes forever when a new hire starts."


def _text(result) -> str:
    content = result.content[0]
    assert isinstance(content, TextContent)
    return content.text


def _json_after_prefix(text: str) -> dict:
    """The tools prefix success messages; take the JSON object that follows."""
    return json.loads(text[text.index("{") :])


async def _quote(client: Client) -> tuple[str, str]:
    await client.call_tool("add_job", {"name": "Onboard"})
    jobs = json.loads(_text(await client.call_tool("get_jobs", {})))
    interview = _json_after_prefix(
        _text(
            await client.call_tool(
                "add_interview",
                {"title": "T", "participant_label": "Ana", "job_id": jobs[0]["id"]},
            )
        )
    )
    quote = _json_after_prefix(
        _text(await client.call_tool("add_quote", {"interview_id": interview["id"], "text": QUOTE}))
    )
    return interview["id"], quote["id"]


@pytest.mark.asyncio
async def test_extract_then_list_candidates() -> None:
    async with Client(mcp) as client:
        interview_id, quote_id = await _quote(client)
        extracted = json.loads(
            _text(await client.call_tool("extract_candidates", {"quote_id": quote_id}))
        )

        listed = json.loads(
            _text(await client.call_tool("list_candidates", {"interview_id": interview_id}))
        )

    assert extracted
    assert len(listed) == len(extracted)
    assert all(c["quote_id"] == quote_id for c in listed)


@pytest.mark.asyncio
async def test_extract_is_idempotent_over_mcp() -> None:
    async with Client(mcp) as client:
        _, quote_id = await _quote(client)
        await client.call_tool("extract_candidates", {"quote_id": quote_id})
        second = json.loads(
            _text(await client.call_tool("extract_candidates", {"quote_id": quote_id}))
        )

    assert second == []


@pytest.mark.asyncio
async def test_extract_unknown_quote_reports_not_found() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("extract_candidates", {"quote_id": "missing"})
    assert _text(result) == "Error: Quote with ID missing not found."


@pytest.mark.asyncio
async def test_update_candidate_reports_unknown_status() -> None:
    async with Client(mcp) as client:
        _, quote_id = await _quote(client)
        candidates = json.loads(
            _text(await client.call_tool("extract_candidates", {"quote_id": quote_id}))
        )
        result = await client.call_tool(
            "update_candidate", {"candidate_id": candidates[0]["id"], "status": "sideways"}
        )
    assert _text(result) == "Error: unknown candidate status: sideways"


@pytest.mark.asyncio
async def test_get_and_delete_candidate() -> None:
    async with Client(mcp) as client:
        _, quote_id = await _quote(client)
        candidates = json.loads(
            _text(await client.call_tool("extract_candidates", {"quote_id": quote_id}))
        )
        candidate_id = candidates[0]["id"]

        fetched = json.loads(
            _text(await client.call_tool("get_candidate", {"candidate_id": candidate_id}))
        )
        deleted = _text(await client.call_tool("delete_candidate", {"candidate_id": candidate_id}))
        missing = _text(await client.call_tool("get_candidate", {"candidate_id": candidate_id}))

    assert fetched["id"] == candidate_id
    assert deleted == f"Candidate deleted successfully: {candidate_id}"
    assert missing == f"Error: Outcome candidate with ID {candidate_id} not found."


@pytest.mark.asyncio
async def test_list_candidates_rejects_unknown_status() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("list_candidates", {"status": "nope"})
    assert _text(result) == "Error: unknown candidate status: nope"
