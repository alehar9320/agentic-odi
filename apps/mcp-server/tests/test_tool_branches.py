"""Branch coverage for MCP tool prompts, errors, and full updates."""

from __future__ import annotations

import json
import re

import pytest
from agentic_odi_mcp_server import mcp
from agentic_odi_mcp_server import mcp_server as server
from fastmcp import Client
from mcp.types import TextContent


def _text(result) -> str:
    content = result.content[0]
    assert isinstance(content, TextContent)
    return content.text


def _extract_id(text: str) -> str:
    match = re.search(r'"id"\s*:\s*"([^"]+)"', text)
    assert match is not None
    return match.group(1)


def _payload(text: str) -> dict:
    match = re.search(r"({.*})", text, re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))


def _customer_value() -> dict:
    return {
        "direction": "minimize",
        "unit_of_measure": "time",
        "object_of_control": "to resolve setup errors",
        "statement": "Minimize the time to resolve setup errors",
        "importance": 8.5,
        "satisfaction": 3.5,
    }


def _business_value() -> dict:
    return {"category": "cost_reduction", "statement": "Saves engineering hours"}


async def _create_customer_outcome(client: Client) -> str:
    await client.call_tool("add_job", {"name": "Onboard"})
    jobs = json.loads(_text(await client.call_tool("get_jobs", {})))
    job_id = jobs[0]["id"]
    result = await client.call_tool(
        "add_customer_outcome",
        {
            "job_id": job_id,
            "customer_value": _customer_value(),
            "business_value": _business_value(),
        },
    )
    return _extract_id(_text(result))


@pytest.mark.asyncio
async def test_assistant_prompt_is_registered() -> None:
    async with Client(mcp) as client:
        prompts = await client.list_prompts()
        result = await client.get_prompt("odi_assistant_prompt")

    assert [prompt.name for prompt in prompts] == ["odi_assistant_prompt"]
    assert getattr(result.messages[0].content, "text", None) == server.ODI_ASSISTANT_PROMPT


@pytest.mark.asyncio
async def test_add_outcome_rejects_out_of_range_scores() -> None:
    async with Client(mcp) as client:
        await client.call_tool("add_job", {"name": "Onboard"})
        jobs = json.loads(_text(await client.call_tool("get_jobs", {})))

        result = await client.call_tool(
            "add_outcome",
            {
                "job_id": jobs[0]["id"],
                "statement": "Minimize onboarding time",
                "importance": 11.0,
                "satisfaction": 5.0,
            },
        )

    assert _text(result) == ("Error: importance and satisfaction must be between 1.0 and 10.0")


@pytest.mark.asyncio
async def test_add_outcome_rejects_a_skip_without_a_reason() -> None:
    async with Client(mcp) as client:
        await client.call_tool("add_job", {"name": "Onboard"})
        jobs = json.loads(_text(await client.call_tool("get_jobs", {})))

        result = await client.call_tool(
            "add_outcome",
            {
                "job_id": jobs[0]["id"],
                "statement": "Minimize the time it takes to onboard when they sign up",
                "importance": 8.0,
                "satisfaction": 5.0,
                "claim_check": {
                    "asked": ["What does it cost?"],
                    "skips": [{"question": "What does it cost?", "reason": ""}],
                },
            },
        )

    text = _text(result)
    assert text.startswith("Error:")
    assert "reason" in text


@pytest.mark.asyncio
async def test_add_customer_outcome_reports_validation_errors() -> None:
    async with Client(mcp) as client:
        await client.call_tool("add_job", {"name": "Onboard"})
        jobs = json.loads(_text(await client.call_tool("get_jobs", {})))

        result = await client.call_tool(
            "add_customer_outcome",
            {
                "job_id": jobs[0]["id"],
                "customer_value": {**_customer_value(), "direction": "sideways"},
                "business_value": _business_value(),
            },
        )

    assert _text(result).startswith("Error: ")


@pytest.mark.asyncio
async def test_update_customer_outcome_reports_missing_ids() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "update_customer_outcome", {"outcome_id": "missing", "importance": 9.0}
        )

    assert _text(result) == "Customer outcome not found: missing"


@pytest.mark.asyncio
async def test_update_customer_outcome_applies_every_field() -> None:
    async with Client(mcp) as client:
        outcome_id = await _create_customer_outcome(client)

        result = await client.call_tool(
            "update_customer_outcome",
            {
                "outcome_id": outcome_id,
                "direction": "maximize",
                "unit_of_measure": "hours",
                "object_of_control": "throughput",
                "contextual_clarifier": "during onboarding",
                "statement": "Maximize onboarding throughput",
                "importance": 9.0,
                "satisfaction": 2.0,
                "category": "retention",
                "business_statement": "Keeps customers",
                "detail": "Expansion revenue",
                "estimated_annual_value": 120000.0,
                "confidence": 0.8,
                "step_id": "step-1",
            },
        )

    data = _payload(_text(result))
    assert data["customer_value"]["direction"] == "maximize"
    assert data["customer_value"]["unit_of_measure"] == "hours"
    assert data["customer_value"]["object_of_control"] == "throughput"
    assert data["customer_value"]["contextual_clarifier"] == "during onboarding"
    assert data["customer_value"]["statement"] == "Maximize onboarding throughput"
    assert data["customer_value"]["importance"] == 9.0
    assert data["customer_value"]["satisfaction"] == 2.0
    assert data["business_value"]["category"] == "retention"
    assert data["business_value"]["statement"] == "Keeps customers"
    assert data["business_value"]["detail"] == "Expansion revenue"
    assert data["business_value"]["estimated_annual_value"] == 120000.0
    assert data["business_value"]["confidence"] == 0.8
    assert data["step_id"] == "step-1"


@pytest.mark.asyncio
async def test_update_customer_outcome_reports_validation_errors() -> None:
    async with Client(mcp) as client:
        outcome_id = await _create_customer_outcome(client)

        result = await client.call_tool(
            "update_customer_outcome",
            {"outcome_id": outcome_id, "category": "not-a-category"},
        )

    assert _text(result).startswith("Error: ")


@pytest.mark.asyncio
async def test_delete_customer_outcome_reports_missing_ids() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("delete_customer_outcome", {"outcome_id": "missing"})

    assert _text(result) == "Customer outcome not found: missing"


def test_main_runs_the_http_transport(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(mcp, "run", lambda **kwargs: calls.append(kwargs))

    server.main([])

    assert calls == [{"transport": "http", "port": 8000}]


def test_main_passes_an_explicit_port_through(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(mcp, "run", lambda **kwargs: calls.append(kwargs))

    server.main(["--port", "8010"])

    assert calls == [{"transport": "http", "port": 8010}]
