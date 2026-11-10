"""W1/ALH-64: record what an opportunity is worth through MCP.

The MCP surface is a thin adapter over one ``ODIService.set_outcome_value``
call. A ``market`` or ``pilot`` basis needs a named source; a missing estimate
stays ``unsized`` and is never read as ``0``; the value is never derived from
the opportunity score.
"""

from __future__ import annotations

import json
import re

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client
from mcp.types import TextContent

_STATEMENT = "Minimize the time it takes to publish a plugin when a release is ready"


def _text(result) -> str:
    content = result.content[0]
    assert isinstance(content, TextContent)
    return content.text


def _payload(text: str) -> dict:
    match = re.search(r"({.*})", text, re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))


async def _seed(client: Client) -> str:
    await client.call_tool("add_job", {"name": "Publish a plugin"})
    job_id = json.loads(_text(await client.call_tool("get_jobs", {})))[0]["id"]
    outcome = _payload(
        _text(
            await client.call_tool(
                "add_outcome",
                {
                    "job_id": job_id,
                    "statement": _STATEMENT,
                    "importance": 9.0,
                    "satisfaction": 3.0,
                },
            )
        )
    )
    return outcome["id"]


@pytest.mark.asyncio
async def test_value_records_a_market_estimate_with_its_source() -> None:
    async with Client(mcp) as client:
        outcome_id = await _seed(client)
        result = _payload(
            _text(
                await client.call_tool(
                    "set_outcome_value",
                    {
                        "outcome_id": outcome_id,
                        "estimate": 250000.0,
                        "unit": "currency",
                        "basis": "market",
                        "source": "Gartner 2025 plugin market report",
                    },
                )
            )
        )
    assert result["value_estimate"] == 250000.0
    assert result["value_unit"] == "currency"
    assert result["value_basis"] == "market"
    assert result["value_source"] == "Gartner 2025 plugin market report"


@pytest.mark.asyncio
async def test_a_market_basis_without_a_source_is_refused() -> None:
    async with Client(mcp) as client:
        outcome_id = await _seed(client)
        text = _text(
            await client.call_tool(
                "set_outcome_value",
                {"outcome_id": outcome_id, "estimate": 1.0, "unit": "currency", "basis": "market"},
            )
        )
    assert "Error" in text
    assert "value_source" in text


@pytest.mark.asyncio
async def test_clearing_the_estimate_leaves_the_outcome_unsized() -> None:
    async with Client(mcp) as client:
        outcome_id = await _seed(client)
        await client.call_tool(
            "set_outcome_value",
            {"outcome_id": outcome_id, "estimate": 100.0, "unit": "users"},
        )
        cleared = _payload(
            _text(
                await client.call_tool(
                    "set_outcome_value", {"outcome_id": outcome_id, "estimate": None}
                )
            )
        )
    assert cleared["value_estimate"] is None
    assert cleared["value_unit"] is None


@pytest.mark.asyncio
async def test_the_value_is_never_derived_from_the_score() -> None:
    async with Client(mcp) as client:
        outcome_id = await _seed(client)
        valued = _payload(
            _text(
                await client.call_tool(
                    "set_outcome_value",
                    {"outcome_id": outcome_id, "estimate": 4.0, "unit": "users"},
                )
            )
        )
    assert valued["value_estimate"] == 4.0
    assert valued["opportunity_score"] == 15.0
