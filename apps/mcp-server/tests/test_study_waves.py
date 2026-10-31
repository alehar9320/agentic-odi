"""Studies and waves round-trip through the live MCP registry (M2-05)."""

import json
from typing import Any

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client

STATEMENT = "Minimize the time it takes to harvest the field when the weather turns"
ADDED = "Minimize the cost of the fuel burned while the tractor is idling"


def _text(result: Any) -> str:
    return result.content[0].text


def _payload(result: Any) -> Any:
    text = _text(result)
    start = min((index for index in (text.find("{"), text.find("[")) if index != -1), default=-1)
    assert start != -1, text
    return json.loads(text[start:])


async def _seed(client: Client) -> tuple[str, dict]:
    job = _payload(await client.call_tool("add_job", {"name": "Corn growers"}))
    wave = _payload(
        await client.call_tool(
            "open_study",
            {
                "job_id": job["id"],
                "name": "Corn growers, quarterly pulse",
                "outcome_statements": [STATEMENT],
                "themes": ["yield"],
            },
        )
    )
    return str(job["id"]), wave


@pytest.mark.asyncio
async def test_open_study_starts_wave_one_and_lists_it() -> None:
    async with Client(mcp) as client:
        job_id, wave = await _seed(client)
        listed = _payload(await client.call_tool("get_studies", {"job_id": job_id}))

    assert wave["wave"] == 1
    assert wave["lineage_id"] == wave["id"]
    assert wave["frame"]["outcome_statements"] == [STATEMENT]
    assert [item["id"] for item in listed] == [wave["id"]]


@pytest.mark.asyncio
async def test_get_studies_is_empty_before_a_study_is_opened() -> None:
    async with Client(mcp) as client:
        await client.call_tool("add_job", {"name": "Corn growers"})
        text = _text(await client.call_tool("get_studies", {}))

    assert json.loads(text) == []


@pytest.mark.asyncio
async def test_next_wave_copies_the_frame_without_the_measurement() -> None:
    async with Client(mcp) as client:
        job_id, wave_one = await _seed(client)
        added = await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": STATEMENT,
                "importance": 8,
                "satisfaction": 4,
                "study_id": wave_one["id"],
            },
        )
        assert not _text(added).startswith("Error:"), _text(added)
        wave_two = _payload(await client.call_tool("next_wave", {"study_id": wave_one["id"]}))

    assert wave_two["wave"] == 2
    assert wave_two["lineage_id"] == wave_one["lineage_id"]
    assert wave_two["frame"] == wave_one["frame"]


@pytest.mark.asyncio
async def test_compare_waves_reports_added_with_a_null_score() -> None:
    async with Client(mcp) as client:
        job_id, wave_one = await _seed(client)
        wave_two = _payload(await client.call_tool("next_wave", {"study_id": wave_one["id"]}))
        await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": ADDED,
                "importance": 6,
                "satisfaction": 3,
                "study_id": wave_two["id"],
            },
        )
        comparison = _payload(
            await client.call_tool(
                "compare_waves", {"study_a": wave_one["id"], "study_b": wave_two["id"]}
            )
        )

    item = next(row for row in comparison["per_outcome"] if row["statement"] == ADDED)
    assert item["status"] == "added"
    assert item["score_a"] is None
    assert item["delta"] is None
    assert comparison["added"] == [ADDED]


@pytest.mark.asyncio
async def test_compare_waves_refuses_two_jobs() -> None:
    async with Client(mcp) as client:
        first = _payload(await client.call_tool("add_job", {"name": "Corn growers"}))
        second = _payload(await client.call_tool("add_job", {"name": "Wheat growers"}))
        wave_a = _payload(
            await client.call_tool("open_study", {"job_id": first["id"], "name": "Corn pulse"})
        )
        wave_b = _payload(
            await client.call_tool("open_study", {"job_id": second["id"], "name": "Wheat pulse"})
        )
        text = _text(
            await client.call_tool(
                "compare_waves", {"study_a": wave_a["id"], "study_b": wave_b["id"]}
            )
        )

    assert text.startswith("Error: ")
    assert "different" in text.lower() or "job" in text.lower()


@pytest.mark.asyncio
async def test_an_unknown_study_is_reported_not_invented() -> None:
    async with Client(mcp) as client:
        text = _text(await client.call_tool("next_wave", {"study_id": "nope"}))

    assert text.startswith("Error: Study with ID nope not found.")
