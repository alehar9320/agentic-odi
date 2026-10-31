"""MCP coverage for the coverage tool (A8 / ALH-21)."""

from __future__ import annotations

import json

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client
from mcp.types import TextContent

STAGES = [
    "define",
    "locate",
    "prepare",
    "confirm",
    "execute",
    "monitor",
    "modify",
    "conclude",
]


def _text(result) -> str:
    content = result.content[0]
    assert isinstance(content, TextContent)
    return content.text


async def _job(client: Client) -> str:
    res = await client.call_tool("add_job", {"name": "Onboard"})
    return json.loads(_text(res).split(": ", 1)[1])["id"]


@pytest.mark.asyncio
async def test_get_coverage_reports_all_stages_and_gaps() -> None:
    async with Client(mcp) as client:
        job_id = await _job(client)

        res = await client.call_tool("get_coverage", {"job_id": job_id})
        report = json.loads(_text(res))

        assert [row["stage"] for row in report["per_stage"]] == STAGES
        assert report["gaps"] == STAGES
        assert report["totals"]["outcomes"] == 0


@pytest.mark.asyncio
async def test_get_coverage_unknown_job_reports_error() -> None:
    async with Client(mcp) as client:
        res = await client.call_tool("get_coverage", {"job_id": "nope"})

        assert "Job not found" in _text(res)
