"""The traceability tools round-trip through the live MCP registry."""

from __future__ import annotations

import json
from typing import Any

import pytest
from agentic_odi_core.models import V2MOM
from agentic_odi_mcp_server import mcp, mcp_server
from fastmcp import Client

_METHOD = "Cut time-to-first-value"


def _text(result: Any) -> str:
    return result.content[0].text


def _payload(result: Any) -> Any:
    """Tool replies are prose-wrapped JSON; take the first JSON value in the text."""
    text = _text(result)
    start = min((index for index in (text.find("{"), text.find("[")) if index != -1), default=-1)
    assert start != -1, text
    return json.loads(text[start:])


async def _seed(client: Client, *, with_vision: bool = True) -> str:
    if with_vision:
        # The vision has no MCP write tool yet (#312 owns that surface).
        mcp_server.service.save_v2mom(V2MOM(vision="Make onboarding painless", methods=[_METHOD]))
    job = _payload(await client.call_tool("add_job", {"name": "Onboard a new engineer"}))
    outcome = _payload(
        await client.call_tool(
            "add_outcome",
            {
                "job_id": job["id"],
                "statement": "Minimize the time it takes to onboard a new engineer when they join",
                "importance": 8,
                "satisfaction": 4,
                "claim_check": {
                    "asked": ["How long does onboarding take today?"],
                    "answers": ["About eight weeks to first real task."],
                    "skips": [],
                },
            },
        )
    )
    return str(outcome["id"])


@pytest.mark.asyncio
async def test_an_empty_vision_says_there_is_nothing_to_check() -> None:
    async with Client(mcp) as client:
        report = _payload(await client.call_tool("get_traceability_report", {}))

    assert report["objectives_defined"] is False
    assert "no objectives defined" in report["message"].lower()


@pytest.mark.asyncio
async def test_linking_round_trips_and_the_report_counts_it() -> None:
    async with Client(mcp) as client:
        outcome_id = await _seed(client)
        linked = _payload(
            await client.call_tool(
                "link_outcome", {"outcome_id": outcome_id, "field": "method", "text": _METHOD}
            )
        )
        alignments = _payload(await client.call_tool("get_outcome_alignments", {}))
        report = _payload(await client.call_tool("get_traceability_report", {}))

    assert linked["trace"][0]["text"] == _METHOD
    assert [item["outcome_id"] for item in alignments] == [outcome_id]
    assert report["counts"] == {"orphans": 0, "unfunded": 0, "drift": 0}


@pytest.mark.asyncio
async def test_linking_unknown_text_is_refused_and_names_what_exists() -> None:
    async with Client(mcp) as client:
        outcome_id = await _seed(client)
        refused = _text(
            await client.call_tool(
                "link_outcome",
                {"outcome_id": outcome_id, "field": "method", "text": "Something else"},
            )
        )

    assert refused.startswith("Error:")
    assert _METHOD in refused


@pytest.mark.asyncio
async def test_unlinking_returns_the_outcome_to_an_orphan() -> None:
    async with Client(mcp) as client:
        outcome_id = await _seed(client)
        linked = _payload(
            await client.call_tool(
                "link_outcome", {"outcome_id": outcome_id, "field": "method", "text": _METHOD}
            )
        )
        key = linked["trace"][0]["key"]
        await client.call_tool(
            "unlink_outcome", {"outcome_id": outcome_id, "field": "method", "key": key}
        )
        report = _payload(await client.call_tool("get_traceability_report", {}))

    assert report["orphans"] == [outcome_id]
