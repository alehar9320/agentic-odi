"""Stage 5 and Stage 6 round-trip through the live MCP registry."""

import json
from typing import Any

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client


def _text(result: Any) -> str:
    return result.content[0].text


def _payload(result: Any) -> Any:
    """Tool replies are prose-wrapped JSON; take the first JSON value in the text."""
    text = _text(result)
    start = min((index for index in (text.find("{"), text.find("[")) if index != -1), default=-1)
    assert start != -1, text
    return json.loads(text[start:])


async def _seed_underserved_job(client: Client) -> str:
    job = _payload(await client.call_tool("add_job", {"name": "Rotate a leaked secret"}))
    step = _payload(
        await client.call_tool(
            "add_step",
            {
                "job_id": job["id"],
                "name": "Gather the current values",
                "order": 2,
                "stage": "locate",
                "allow_empty_job_map": True,
            },
        )
    )
    for statement, importance, satisfaction in (
        (
            "Minimize the time it takes to gather every value from the vault when rotating in "
            "a hospital",
            9,
            2,
        ),
        (
            "Minimize the number of values missed after rotation when rotating in a hospital",
            8,
            3,
        ),
    ):
        added = await client.call_tool(
            "add_outcome",
            {
                "job_id": job["id"],
                "statement": statement,
                "importance": importance,
                "satisfaction": satisfaction,
                "step_id": step["id"],
                "claim_check": {
                    "asked": ["How important is this?"],
                    "answers": ["Very"],
                },
            },
        )
        text = _text(added)
        assert not text.startswith("Error:"), text
    return str(job["id"])


@pytest.mark.asyncio
async def test_segment_market_clusters_scored_outcomes_by_step() -> None:
    async with Client(mcp) as client:
        job_id = await _seed_underserved_job(client)
        assert _payload(await client.call_tool("get_segments", {})) == []

        segments = _payload(await client.call_tool("segment_market", {"job_id": job_id}))
        listed = _payload(await client.call_tool("get_segments", {"job_id": job_id}))

    assert len(segments) == 1
    assert [item["id"] for item in listed] == [segments[0]["id"]]
    segment = segments[0]
    assert segment["verdict"] == "underserved"
    assert segment["confidence"] > 0
    assert len(segment["outcome_ids"]) == 2
    assert "Gather the current values" in segment["name"]


@pytest.mark.asyncio
async def test_re_running_updates_the_same_segment_instead_of_stacking() -> None:
    async with Client(mcp) as client:
        job_id = await _seed_underserved_job(client)
        first = _payload(await client.call_tool("segment_market", {"job_id": job_id}))
        second = _payload(await client.call_tool("segment_market", {"job_id": job_id}))
        listed = _payload(await client.call_tool("get_segments", {}))

    assert [item["id"] for item in first] == [item["id"] for item in second]
    assert len(listed) == 1


@pytest.mark.asyncio
async def test_an_unknown_job_is_reported_not_segmented() -> None:
    async with Client(mcp) as client:
        text = _text(await client.call_tool("segment_market", {"job_id": "nope"}))

    assert text.startswith("Job not found: nope")


@pytest.mark.asyncio
async def test_propose_strategy_returns_one_path_with_the_paths_it_beat() -> None:
    async with Client(mcp) as client:
        job_id = await _seed_underserved_job(client)
        # A served outcome on the same job gives the differentiated path something to borrow.
        served = await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time it takes to verify the new value when deploying",
                "importance": 5,
                "satisfaction": 5,
                "claim_check": {
                    "asked": ["How long does verification take?"],
                    "answers": ["A few minutes"],
                },
            },
        )
        assert not _text(served).startswith("Error:"), _text(served)
        await client.call_tool("segment_market", {"job_id": job_id})

        strategy = _payload(await client.call_tool("propose_strategy", {"job_id": job_id}))
        recorded = _payload(await client.call_tool("get_strategy", {}))
        again = _payload(await client.call_tool("propose_strategy", {}))

    assert strategy["kind"] in {"differentiated", "disruptive", "new_market"}
    assert {item["kind"] for item in strategy["rejected"]} == {
        kind for kind in ("differentiated", "disruptive", "new_market") if kind != strategy["kind"]
    }
    assert all(item["why"] for item in strategy["rejected"])
    assert recorded["id"] == strategy["id"]
    assert again["id"] == strategy["id"]


@pytest.mark.asyncio
async def test_get_strategy_answers_null_until_stage_6_runs() -> None:
    async with Client(mcp) as client:
        text = _text(await client.call_tool("get_strategy", {}))

    assert text == "null"


@pytest.mark.asyncio
async def test_propose_strategy_refuses_without_evidence_rather_than_inventing_a_bet() -> None:
    async with Client(mcp) as client:
        await client.call_tool("add_job", {"name": "Rotate a leaked secret"})
        text = _text(await client.call_tool("propose_strategy", {}))

    assert text.startswith("Error: Invalid strategy request: No path is supported yet:")
    assert "Score outcomes against a job map" in text
