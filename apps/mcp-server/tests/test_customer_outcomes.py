"""Tests for Customer Outcome entities."""

import json

import pytest
from agentic_odi_mcp_server.mcp_server import mcp
from fastmcp import Client


@pytest.mark.asyncio
async def test_add_customer_outcome_creates_and_computes_opportunity_score():
    async with Client(mcp) as client:
        await client.call_tool("add_job", {"name": "Onboard", "description": "Dev onboarding"})
        jobs_result = await client.call_tool("get_jobs", {})
        jobs = json.loads(jobs_result.content[0].text)  # type: ignore[index]
        job_id = jobs[0]["id"]

        cv = {
            "direction": "minimize",
            "unit_of_measure": "time",
            "object_of_control": "to setup",
            "statement": "Minimize time to setup",
            "importance": 8.5,
            "satisfaction": 4.0,
        }
        bv = {
            "category": "cost_reduction",
            "statement": "Saves developer hours",
        }
        res = await client.call_tool(
            "add_customer_outcome", {"job_id": job_id, "customer_value": cv, "business_value": bv}
        )
        text = res.content[0].text  # type: ignore[index]
        assert "Customer outcome created successfully" in text
        assert '"opportunity_score":13.0' in text


@pytest.mark.asyncio
async def test_add_customer_outcome_job_not_found_returns_error():
    async with Client(mcp) as client:
        cv = {
            "direction": "minimize",
            "unit_of_measure": "time",
            "object_of_control": "x",
            "statement": "x",
            "importance": 5,
            "satisfaction": 5,
        }
        bv = {"category": "cost_reduction", "statement": "y"}
        res = await client.call_tool(
            "add_customer_outcome",
            {"job_id": "nope", "customer_value": cv, "business_value": bv},
        )
        assert "Error: Job with ID nope not found." in res.content[0].text  # type: ignore[index]


@pytest.mark.asyncio
async def test_get_list_update_delete_flow():
    async with Client(mcp) as client:
        await client.call_tool("add_job", {"name": "Onboard"})
        jobs = json.loads((await client.call_tool("get_jobs", {})).content[0].text)  # type: ignore[index]
        job_id = jobs[0]["id"]

        cv = {
            "direction": "minimize",
            "unit_of_measure": "time",
            "object_of_control": "x",
            "statement": "Minimize x",
            "importance": 7,
            "satisfaction": 3,
        }
        bv = {"category": "retention", "statement": "Retains users"}
        res = await client.call_tool(
            "add_customer_outcome", {"job_id": job_id, "customer_value": cv, "business_value": bv}
        )
        out = json.loads(res.content[0].text.replace("Customer outcome created successfully: ", ""))
        oid = out["id"]

        got = await client.call_tool("get_customer_outcome", {"outcome_id": oid})
        assert oid in got.content[0].text  # type: ignore[index]

        listed = await client.call_tool("list_customer_outcomes", {})
        assert oid in listed.content[0].text  # type: ignore[index]

        filtered = await client.call_tool("list_customer_outcomes", {"job_id": job_id})
        assert oid in filtered.content[0].text  # type: ignore[index]

        upd = await client.call_tool(
            "update_customer_outcome", {"outcome_id": oid, "step_id": "step-1"}
        )
        assert "updated successfully" in upd.content[0].text  # type: ignore[index]

        dele = await client.call_tool("delete_customer_outcome", {"outcome_id": oid})
        assert "deleted successfully" in dele.content[0].text  # type: ignore[index]

        notfound = await client.call_tool("get_customer_outcome", {"outcome_id": oid})
        assert "not found" in notfound.content[0].text  # type: ignore[index]


@pytest.mark.asyncio
async def test_compute_opportunity_tool():
    async with Client(mcp) as client:
        res = await client.call_tool("compute_opportunity", {"importance": 8, "satisfaction": 2})
        assert "14.00" in str(res.content[0].text)


@pytest.mark.asyncio
async def test_get_capabilities_mentions_customer_outcomes():
    async with Client(mcp) as client:
        res = await client.call_tool("get_capabilities", {})
        text = res.content[0].text  # type: ignore[index]
        assert "add_customer_outcome" in text
        assert "list_customer_outcomes" in text


@pytest.mark.asyncio
async def test_compute_opportunity_out_of_range():
    async with Client(mcp) as client:
        res = await client.call_tool("compute_opportunity", {"importance": 11, "satisfaction": 5})
        assert "Error" in res.content[0].text  # type: ignore[index]


@pytest.mark.asyncio
async def test_update_partial_merge():
    async with Client(mcp) as client:
        await client.call_tool("add_job", {"name": "J"})
        jobs = json.loads((await client.call_tool("get_jobs", {})).content[0].text)  # type: ignore[index]
        job_id = jobs[0]["id"]
        cv = {
            "direction": "minimize",
            "unit_of_measure": "time",
            "object_of_control": "x",
            "statement": "Min x",
            "importance": 5,
            "satisfaction": 5,
        }
        bv = {"category": "cost_reduction", "statement": "Save"}
        out = json.loads(
            (
                await client.call_tool(
                    "add_customer_outcome",
                    {"job_id": job_id, "customer_value": cv, "business_value": bv},
                )
            )
            .content[0]
            .text.replace("Customer outcome created successfully: ", "")
        )
        oid = out["id"]
        upd = await client.call_tool(
            "update_customer_outcome", {"outcome_id": oid, "importance": 8.5}
        )
        assert "updated successfully" in upd.content[0].text  # type: ignore[index]
