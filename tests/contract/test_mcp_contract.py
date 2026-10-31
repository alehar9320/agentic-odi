"""Keep the live MCP surface in lockstep with the core contract."""

from __future__ import annotations

import pytest
from agentic_odi_core.contract import TOOL_SPECS
from agentic_odi_mcp_server.mcp_server import mcp
from fastmcp import Client


@pytest.mark.asyncio
async def test_mcp_exposes_exactly_the_contract_tools() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert {tool.name for tool in tools} == set(TOOL_SPECS)


@pytest.mark.asyncio
async def test_mcp_argument_names_match_the_contract() -> None:
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    for name, spec in TOOL_SPECS.items():
        schema = tools[name].input_schema
        assert set(schema.get("properties", {})) == set(spec.arguments), name
        assert set(schema.get("required", [])) == set(spec.required), name


def test_add_outcome_exposes_sample_metadata() -> None:
    assert {"importance_n", "satisfaction_n", "score_method"} <= set(
        TOOL_SPECS["add_outcome"].arguments
    )


def test_update_outcome_exposes_sample_metadata() -> None:
    assert {"importance_n", "satisfaction_n", "score_method"} <= set(
        TOOL_SPECS["update_outcome"].arguments
    )
