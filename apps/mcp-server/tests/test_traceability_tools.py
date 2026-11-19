"""The traceability tools round-trip through the live MCP registry."""

from __future__ import annotations

import json
from typing import Any

import pytest
from agentic_odi_core.models import V2MOM
from agentic_odi_mcp_server import mcp, mcp_server
from fastmcp import Client
from mcp_failures import sentence

_METHOD = "Cut time-to-first-value"
_MEASURE = "Net revenue retention above 120%"


def _text(result: Any) -> str:
    return result.content[0].text


def _payload(result: Any) -> Any:
    """Tool replies are prose-wrapped JSON; take the first JSON value in the text."""
    text = _text(result)
    start = min((index for index in (text.find("{"), text.find("[")) if index != -1), default=-1)
    assert start != -1, text
    return json.loads(text[start:])


def _seed_vision() -> None:
    # The vision has no MCP write tool yet (#312 owns that surface), so the test
    # seeds it through the same service the tools read.
    mcp_server.service.save_v2mom(V2MOM(vision="Make onboarding painless", methods=[_METHOD]))


async def _seed_outcome(client: Client) -> str:
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
    mcp_server.service.repo.v2mom.clear()
    async with Client(mcp) as client:
        report = _payload(await client.call_tool("get_traceability_report", {}))

    assert report["objectives_defined"] is False
    assert "no objectives defined" in report["message"].lower()


@pytest.mark.asyncio
async def test_linking_round_trips_and_the_report_counts_it() -> None:
    _seed_vision()
    async with Client(mcp) as client:
        outcome_id = await _seed_outcome(client)
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
    _seed_vision()
    async with Client(mcp) as client:
        outcome_id = await _seed_outcome(client)
        refused = _text(
            await client.call_tool(
                "link_outcome",
                {"outcome_id": outcome_id, "field": "method", "text": "Something else"},
            )
        )

    # The handler answers through _fail(); the prose lives in the envelope.
    assert sentence(refused).startswith("Error:")
    assert _METHOD in refused


@pytest.mark.asyncio
async def test_unlinking_returns_the_outcome_to_an_orphan() -> None:
    _seed_vision()
    async with Client(mcp) as client:
        outcome_id = await _seed_outcome(client)
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


@pytest.mark.asyncio
async def test_add_outcome_records_objectives_in_one_write() -> None:
    """#590: the link travels with the outcome, not in a second call."""
    _seed_vision()
    async with Client(mcp) as client:
        job = _payload(await client.call_tool("add_job", {"name": "Onboard a new engineer"}))
        outcome = _payload(
            await client.call_tool(
                "add_outcome",
                {
                    "job_id": job["id"],
                    "statement": (
                        "Minimize the time it takes to onboard a new engineer when they join"
                    ),
                    "importance": 8,
                    "satisfaction": 4,
                    "claim_check": {
                        "asked": ["How long does onboarding take today?"],
                        "answers": ["About eight weeks to first real task."],
                        "skips": [],
                    },
                    "objectives": [{"field": "method", "text": _METHOD}],
                },
            )
        )
        report = _payload(await client.call_tool("get_traceability_report", {}))

    assert outcome["trace"][0]["text"] == _METHOD
    assert report["counts"] == {"orphans": 0, "unfunded": 0, "drift": 0}


@pytest.mark.asyncio
async def test_add_outcome_refuses_an_unknown_objective_and_names_what_exists() -> None:
    _seed_vision()
    async with Client(mcp) as client:
        job = _payload(await client.call_tool("add_job", {"name": "Onboard a new engineer"}))
        refused = _text(
            await client.call_tool(
                "add_outcome",
                {
                    "job_id": job["id"],
                    "statement": (
                        "Minimize the time it takes to onboard a new engineer when they join"
                    ),
                    "objectives": [{"field": "method", "text": "Ship the abandoned wizard"}],
                },
            )
        )

    assert sentence(refused).startswith("Error:")
    assert _METHOD in refused


@pytest.mark.asyncio
async def test_update_outcome_replaces_the_objectives() -> None:
    mcp_server.service.save_v2mom(
        V2MOM(vision="Make onboarding painless", methods=[_METHOD], measures=[_MEASURE])
    )
    async with Client(mcp) as client:
        job = _payload(await client.call_tool("add_job", {"name": "Onboard a new engineer"}))
        outcome = _payload(
            await client.call_tool(
                "add_outcome",
                {
                    "job_id": job["id"],
                    "statement": (
                        "Minimize the time it takes to onboard a new engineer when they join"
                    ),
                    "importance": 8,
                    "satisfaction": 4,
                    "claim_check": {"asked": ["How long?"], "answers": ["Weeks"]},
                    "objectives": [{"field": "method", "text": _METHOD}],
                },
            )
        )
        updated = _payload(
            await client.call_tool(
                "update_outcome",
                {
                    "outcome_id": outcome["id"],
                    "objectives": [{"field": "measure", "text": _MEASURE}],
                },
            )
        )

    assert [link["text"] for link in updated["trace"]] == [_MEASURE]
