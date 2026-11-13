"""Pillar 3 through the MCP registry: a strategy must name the paths it beat.

``choose_strategy`` refuses a strategy with no rejected path — that refusal is
the spec, not an obstacle — so it has to be reachable through the tool and the
tool has to carry the rejected paths through. A miss on any of the record tools
names the id it could not find instead of replying with an empty success.
"""

import json
from typing import Any

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client


def _text(result: Any) -> str:
    return result.content[0].text


def _payload(result: Any) -> Any:
    text = _text(result)
    start = min((index for index in (text.find("{"), text.find("[")) if index != -1), default=-1)
    assert start != -1, text
    return json.loads(text[start:])


async def _seed_segment(client: Client) -> str:
    job = _payload(await client.call_tool("add_job", {"name": "Rotate a leaked secret"}))
    step = _payload(
        await client.call_tool(
            "add_step",
            {
                "job_id": job["id"],
                "name": "Gather the current values",
                "order": 1,
                "stage": "locate",
                "allow_empty_job_map": True,
            },
        )
    )
    for statement, importance, satisfaction in (
        (
            "Minimize the time it takes to rotate the secret when it leaks in a hospital",
            9,
            2,
        ),
        (
            "Minimize the number of values missed after rotation when rotating in a hospital",
            9,
            3,
        ),
        (
            "Minimize the number of steps it takes to audit a rotated secret when it rotates",
            9,
            2,
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
    segments = _payload(await client.call_tool("segment_market", {"job_id": job["id"]}))
    assert segments, segments
    return str(segments[0]["id"])


@pytest.mark.asyncio
async def test_choose_strategy_carries_the_rejected_paths_through_the_tool() -> None:
    async with Client(mcp) as client:
        segment_id = await _seed_segment(client)
        recorded = _text(
            await client.call_tool(
                "choose_strategy",
                {
                    "segment_id": segment_id,
                    "kind": "differentiated",
                    "rationale": "The rotation path is underserved and nobody serves it well.",
                    "expected_effect": "Cut the time to rotate a leaked secret.",
                    "rejected": [
                        {"kind": "disruptive", "why": "No non-consumer is priced out of rotation."},
                        {"kind": "new_market", "why": "No evidence of non-consumption."},
                    ],
                },
            )
        )
        assert recorded.startswith("Strategy recorded:"), recorded
        strategy = _payload(await client.call_tool("list_strategies", {"segment_id": segment_id}))

    assert {entry["kind"] for entry in strategy[0]["rejected"]} == {"disruptive", "new_market"}
    assert all(entry["why"] for entry in strategy[0]["rejected"])


@pytest.mark.asyncio
async def test_choose_strategy_refuses_a_strategy_with_no_rejected_path() -> None:
    async with Client(mcp) as client:
        segment_id = await _seed_segment(client)
        refused = _text(
            await client.call_tool(
                "choose_strategy",
                {
                    "segment_id": segment_id,
                    "kind": "differentiated",
                    "rationale": "Only one path was considered.",
                    "expected_effect": "Ship it.",
                },
            )
        )
        missing = _text(await client.call_tool("get_bet", {"bet_id": "no-such-bet"}))

    assert "rejected alternatives" in refused, refused
    assert missing == "Error: Bet with ID no-such-bet not found."
