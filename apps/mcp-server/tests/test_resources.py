"""The read-only ``odi://`` surface: parity, paging, errors, and honesty."""

import json
from typing import Any

import pytest
from agentic_odi_mcp_server.mcp_server import mcp, service
from fastmcp import Client

# The in-memory client wraps a handler's ResourceError in the protocol error,
# keeping the message the handler raised. Tests assert on that message.


def _document(contents: list[Any]) -> dict[str, Any]:
    return json.loads(contents[0].text)


def _seed() -> tuple[str, list[str]]:
    job = service.add_job(name="Plan a trip")
    outcomes = [
        service.add_outcome(
            job_id=job.id,
            statement=(
                "Minimize the time it takes to plan a weekend trip when the weather is unknown"
            ),
            importance=8.6,
            satisfaction=4.9,
        ),
        service.add_outcome(
            job_id=job.id,
            statement=("Maximize the likelihood of staying within budget when booking travel"),
            importance=5.0,
            satisfaction=6.0,
        ),
    ]
    for index in range(4):
        service.add_evidence(
            source_name=f"interview-{index}",
            source_kind="manual",
            name=f"quote {index}",
            content="We reconcile the invoices by hand every month.",
        )
    return job.id, [outcome.id for outcome in outcomes]


@pytest.mark.asyncio
async def test_landscape_counts_and_ranking_match_the_store() -> None:
    _, outcome_ids = _seed()

    async with Client(mcp) as client:
        document = _document(await client.read_resource("odi://landscape"))

    assert document["source"] == "local"
    assert document["counts"] == {"jobs": 1, "outcomes": 2, "underserved": 1}
    assert {row["id"] for row in document["outcomes"]} == set(outcome_ids)
    # 8.6 + max(8.6 - 4.9, 0) = 12.3 ranks above 5.0.
    assert document["outcomes"][0]["id"] == outcome_ids[0]
    assert document["outcomes"][0]["opportunity_score"] == pytest.approx(12.3)


@pytest.mark.asyncio
async def test_empty_store_returns_an_honest_empty_landscape() -> None:
    async with Client(mcp) as client:
        document = _document(await client.read_resource("odi://landscape"))

    assert document["jobs"] == []
    assert document["outcomes"] == []
    assert document["counts"] == {"jobs": 0, "outcomes": 0, "underserved": 0}
    assert document["source"] == "local"


@pytest.mark.asyncio
async def test_unknown_job_raises_instead_of_returning_an_empty_body() -> None:
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="Job not found: missing"):
            await client.read_resource("odi://jobs/missing")


@pytest.mark.asyncio
async def test_job_resource_matches_its_read_tool() -> None:
    job_id, _ = _seed()

    async with Client(mcp) as client:
        resource = _document(await client.read_resource(f"odi://jobs/{job_id}"))
        result = await client.call_tool("get_job", {"job_id": job_id})

    assert resource == json.loads(result.content[0].text)


@pytest.mark.asyncio
async def test_evidence_paging_reports_the_next_offset_and_stops_at_the_end() -> None:
    _seed()

    async with Client(mcp) as client:
        first = _document(await client.read_resource("odi://evidence?limit=2&offset=0"))
        last = _document(await client.read_resource("odi://evidence?limit=2&offset=2"))

    assert first["page"] == {"limit": 2, "offset": 0, "total": 4, "next_offset": 2}
    assert len(first["items"]) == 2
    assert last["page"] == {"limit": 2, "offset": 2, "total": 4, "next_offset": None}
    assert len(last["items"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, 1000])
async def test_out_of_range_limits_are_rejected_with_the_range(limit: int) -> None:
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="between 1 and 100"):
            await client.read_resource(f"odi://evidence?limit={limit}")


@pytest.mark.asyncio
async def test_vision_raises_naming_the_missing_store() -> None:
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="no brief store exists"):
            await client.read_resource("odi://vision")
