"""Keep the live MCP surface in lockstep with the core contract.

A failure is part of that surface. These tests round-trip each kind of failure
through the text a tool actually returns, so "the client can tell needs-consent
from broke" is a checked property and not a hope.
"""

from __future__ import annotations

import json

import pytest
from agentic_odi_core.contract import TOOL_SPECS
from agentic_odi_core.errors import (
    ConflictError,
    ConsentRequired,
    RateLimitError,
    StoreError,
    ValidationError,
)
from agentic_odi_core.remote import StudioErrorCode, error_envelope, parse_tool_result
from agentic_odi_core.services import ValueOutOfRangeError
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


def _envelope_text(exc: BaseException) -> str:
    """The text a failing tool returns, built the way the server builds it."""
    envelope = error_envelope(exc)
    return json.dumps({"error": envelope, "message": f"Error: {envelope['message']}"})


@pytest.mark.parametrize(
    ("exc", "code", "retryable"),
    [
        (ValidationError("the statement is not in ODI form"), "validation", False),
        (ValueOutOfRangeError("scores must be between 1.0 and 10.0"), "out_of_range", False),
        (ConflictError("that outcome is already recorded"), "conflict", False),
        (ConsentRequired("the PM has not approved this workspace"), "consent_required", False),
        (RateLimitError("too many requests"), "rate_limited", True),
        (StoreError("the event log is unwritable"), "internal", False),
    ],
    ids=["validation", "out-of-range", "conflict", "consent", "rate-limit", "store"],
)
def test_each_failure_kind_arrives_with_a_code_of_its_own(
    exc: BaseException, code: str, retryable: bool
) -> None:
    """No two kinds collapse into one verdict.

    That collapse is what #460 exists to remove, and #458 is blocked behind it:
    a client that cannot tell needs-consent from broke cannot ask for consent.
    """
    error = parse_tool_result(_envelope_text(exc))

    assert error is not None
    assert error.code.value == code
    assert error.retryable is retryable


@pytest.mark.asyncio
async def test_a_missing_job_crosses_the_wire_as_not_found() -> None:
    """One live call proves the envelope survives the transport, not just the function."""
    async with Client(mcp) as client:
        text = (await client.call_tool("get_job", {"job_id": "nope"})).content[0].text

    error = parse_tool_result(text)

    assert error is not None
    assert error.code is StudioErrorCode.NOT_FOUND
    assert error.retryable is False
