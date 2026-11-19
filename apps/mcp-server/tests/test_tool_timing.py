"""Every MCP tool call emits one timing line, so a slow tool is visible."""

from __future__ import annotations

import logging

import pytest
from fastmcp import Client

LOGGER = "agentic_odi_mcp_server.mcp_server"


@pytest.mark.asyncio
async def test_a_tool_call_logs_its_name_duration_and_outcome(mcp, caplog) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER):
        async with Client(mcp) as client:
            await client.call_tool("get_health", {})

    lines = [record.getMessage() for record in caplog.records if record.name == LOGGER]
    timing = next(line for line in lines if line.startswith("mcp.tool"))
    assert "name=get_health" in timing
    assert "duration_ms=" in timing
    assert "outcome=ok" in timing


@pytest.mark.asyncio
async def test_a_failing_tool_logs_an_error_outcome_with_the_envelope_code(mcp, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        async with Client(mcp) as client:
            await client.call_tool("get_job", {"job_id": "JOB-does-not-exist"})

    lines = [record.getMessage() for record in caplog.records if record.name == LOGGER]
    timing = next(line for line in lines if line.startswith("mcp.tool"))
    assert "name=get_job" in timing
    assert "outcome=error" in timing
    assert "code=not_found" in timing
