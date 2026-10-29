from __future__ import annotations

import json

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client


def _json(text: str) -> dict:
    return json.loads(text)


def _payload(text: str) -> dict:
    return json.loads(text.split(": ", 1)[1])


async def _new_job(client) -> str:
    res = await client.call_tool("add_job", {"name": "Onboard customers"})
    return _payload(res.content[0].text)["id"]  # type: ignore[index]


@pytest.mark.asyncio
async def test_tool_catalog_exposes_context_and_evidence_tools():
    async with Client(mcp) as client:
        names = {tool.name for tool in await client.list_tools()}

    assert {
        "get_job_map",
        "evaluate_outcome",
        "get_odi_schema",
        "add_evidence",
        "list_evidence",
        "promote_evidence",
    } <= names
    assert "greet" not in names


@pytest.mark.asyncio
async def test_evaluate_outcome_accepts_well_formed_statement():
    async with Client(mcp) as client:
        res = await client.call_tool(
            "evaluate_outcome",
            {"statement": "Minimize the time to onboard a customer when they sign up"},
        )

        result = _json(res.content[0].text)  # type: ignore[index]

    assert result["valid"] is True
    assert result["direction"] == "minimize"
    assert result["issues"] == []


@pytest.mark.asyncio
async def test_evaluate_outcome_reports_format_issues():
    async with Client(mcp) as client:
        res = await client.call_tool("evaluate_outcome", {"statement": "Make it better"})

        result = _json(res.content[0].text)  # type: ignore[index]

    assert result["valid"] is False
    assert result["direction"] is None
    assert any("Minimize" in issue for issue in result["issues"])
    assert any("context" in issue.lower() for issue in result["issues"])


@pytest.mark.asyncio
async def test_evaluate_outcome_includes_existing_job_outcomes():
    async with Client(mcp) as client:
        job_id = await _new_job(client)
        await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time to first value when releasing",
                "importance": 8,
                "satisfaction": 4,
            },
        )

        res = await client.call_tool(
            "evaluate_outcome",
            {
                "statement": "Maximize the share of customers reaching first value when onboarding",
                "job_id": job_id,
            },
        )
        result = _json(res.content[0].text)  # type: ignore[index]

    assert result["job_id"] == job_id
    assert (
        result["existing_outcomes"][0]["statement"]
        == "Minimize the time to first value when releasing"
    )


@pytest.mark.asyncio
async def test_get_odi_schema_returns_every_entity():
    async with Client(mcp) as client:
        res = await client.call_tool("get_odi_schema", {})
        schema = _json(res.content[0].text)  # type: ignore[index]

    assert {"Job", "Step", "Outcome", "CustomerOutcome", "Evidence"} <= set(schema)


@pytest.mark.asyncio
async def test_evidence_lifecycle_over_mcp():
    async with Client(mcp) as client:
        job_id = await _new_job(client)
        created = await client.call_tool(
            "add_evidence",
            {
                "source_name": "gong",
                "source_kind": "mcp",
                "item_type": "resource",
                "name": "feedback",
                "content": "Onboarding took two hours",
                "job_id": job_id,
            },
        )
        evidence_id = _payload(created.content[0].text)["id"]  # type: ignore[index]

        listed = await client.call_tool("list_evidence", {"job_id": job_id})
        assert evidence_id in listed.content[0].text  # type: ignore[index]

        fetched = await client.call_tool("get_evidence", {"evidence_id": evidence_id})
        assert "Onboarding took two hours" in fetched.content[0].text  # type: ignore[index]

        promoted = await client.call_tool(
            "promote_evidence",
            {
                "evidence_id": evidence_id,
                "target": "outcome",
                "job_id": job_id,
                "statement": "Minimize the time to onboard a customer when signing up",
                "importance": 8,
                "satisfaction": 4,
            },
        )
        assert "Outcome created successfully" in promoted.content[0].text  # type: ignore[index]
        assert '"opportunity_score":12.0' in promoted.content[0].text  # type: ignore[index]

        deleted = await client.call_tool("delete_evidence", {"evidence_id": evidence_id})
        assert "deleted successfully" in deleted.content[0].text  # type: ignore[index]


@pytest.mark.asyncio
async def test_evidence_tools_report_not_found():
    async with Client(mcp) as client:
        missing = "no-such-evidence"
        assert (
            "not found"
            in (await client.call_tool("get_evidence", {"evidence_id": missing})).content[0].text
        )  # type: ignore[index]
        assert (
            "not found"
            in (await client.call_tool("delete_evidence", {"evidence_id": missing})).content[0].text
        )  # type: ignore[index]
