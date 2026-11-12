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


@pytest.mark.asyncio
async def test_accept_candidate_returns_outcome_and_verbatim_evidence() -> None:
    async with Client(mcp) as client:
        _, quote_id = await _quote(client)
        candidates = json.loads(
            _text(await client.call_tool("extract_candidates", {"quote_id": quote_id}))
        )
        candidate = candidates[0]

        result = json.loads(
            _text(
                await client.call_tool(
                    "accept_candidate",
                    {
                        "candidate_id": candidate["id"],
                        "importance": 8.0,
                        "satisfaction": 3.0,
                    },
                )
            )
        )
        evidence = json.loads(
            _text(await client.call_tool("list_evidence", {"outcome_id": result["outcome"]["id"]}))
        )

    assert result["candidate"]["status"] == "accepted"
    assert result["candidate"]["outcome_id"] == result["outcome"]["id"]
    assert result["evidence"]["content"] == QUOTE
    assert result["evidence"]["source_kind"] == "interview"
    assert len(evidence) == 1


@pytest.mark.asyncio
async def test_accept_candidate_twice_does_not_duplicate_the_outcome() -> None:
    async with Client(mcp) as client:
        _, quote_id = await _quote(client)
        candidates = json.loads(
            _text(await client.call_tool("extract_candidates", {"quote_id": quote_id}))
        )
        candidate_id = candidates[0]["id"]
        args = {"candidate_id": candidate_id, "importance": 8.0, "satisfaction": 3.0}

        first = json.loads(_text(await client.call_tool("accept_candidate", args)))
        second = json.loads(_text(await client.call_tool("accept_candidate", args)))
        outcomes = json.loads(
            _text(await client.call_tool("get_outcomes", {"job_id": first["outcome"]["job_id"]}))
        )

    assert first["outcome"]["id"] == second["outcome"]["id"]
    assert first["evidence"]["id"] == second["evidence"]["id"]
    assert len(outcomes) == 1


@pytest.mark.asyncio
async def test_reject_candidate_requires_a_reason_and_keeps_the_candidate() -> None:
    async with Client(mcp) as client:
        _, quote_id = await _quote(client)
        candidates = json.loads(
            _text(await client.call_tool("extract_candidates", {"quote_id": quote_id}))
        )
        candidate_id = candidates[0]["id"]

        refused = await client.call_tool(
            "reject_candidate", {"candidate_id": candidate_id, "reason": "   "}
        )
        rejected = json.loads(
            _text(
                await client.call_tool(
                    "reject_candidate", {"candidate_id": candidate_id, "reason": "not a need"}
                )
            )
        )
        kept = json.loads(
            _text(await client.call_tool("get_candidate", {"candidate_id": candidate_id}))
        )

    assert _text(refused).startswith("Error: A rejection reason is required")
    assert rejected["status"] == "rejected"
    assert rejected["decision_reason"] == "not a need"
    assert kept["quote_id"] == candidates[0]["quote_id"]


@pytest.mark.asyncio
async def test_accept_candidate_reports_a_missing_candidate() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "accept_candidate", {"candidate_id": "missing", "importance": 8.0, "satisfaction": 3.0}
        )
    assert _text(result) == "Error: Outcome candidate with ID missing not found."
