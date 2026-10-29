import json
import re

import pytest
from agentic_odi_mcp_server import jobs_db, mcp
from fastmcp import Client


def extract_id(result_str):
    match = re.search(r'"id"\s*:\s*"([^"]+)"', result_str)
    return match.group(1) if match else None


@pytest.mark.asyncio
async def test_add_outcome_records_sample_metadata():
    async with Client(mcp) as client:
        job_text = (
            await client.call_tool("add_job", {"name": "Onboard customers", "description": ""})
        ).content[0].text
        job_id = extract_id(job_text)

        survey_text = (
            await client.call_tool(
                "add_outcome",
                {
                    "job_id": job_id,
                    "statement": "Minimize the time it takes to onboard a customer when they sign up",
                    "importance": 8.0,
                    "satisfaction": 6.0,
                    "importance_n": 40,
                    "satisfaction_n": 40,
                    "score_method": "survey",
                },
            )
        ).content[0].text
        assert "Outcome created successfully" in survey_text
        assert '"score_method":"survey"' in survey_text
        assert '"importance_n":40' in survey_text


@pytest.mark.asyncio
async def test_add_outcome_refuses_an_estimate_with_a_count():
    async with Client(mcp) as client:
        job_text = (
            await client.call_tool("add_job", {"name": "Onboard customers", "description": ""})
        ).content[0].text
        job_id = extract_id(job_text)

        text = (
            await client.call_tool(
                "add_outcome",
                {
                    "job_id": job_id,
                    "statement": "Minimize the time it takes to onboard a customer when they sign up",
                    "importance": 8.0,
                    "satisfaction": 6.0,
                    "importance_n": 40,
                },
            )
        ).content[0].text
        assert text.startswith("Error:")


@pytest.mark.asyncio
async def test_odi_workflow():
    """Test the full ODI workflow (Add Job -> Add Steps -> Add Outcome -> Get Data)."""
    # Use in-memory testing by passing the server instance directly to the client
    async with Client(mcp) as client:
        # 1. Add a Job
        job_result = await client.call_tool(
            "add_job", {"name": "Listen to music", "description": "Listen to music on the go"}
        )
        job_text = job_result.content[0].text
        assert "Job created successfully" in job_text

        job_id = extract_id(job_text)
        assert job_id in jobs_db

        # 2. Add an Outcome first (steps require an outcome to exist)
        outcome_res = await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time it takes to find a specific song when searching the catalog",
                "importance": 8.5,
                "satisfaction": 4.0,
            },
        )
        outcome_text = outcome_res.content[0].text
        assert "Outcome created successfully" in outcome_text

        # 3. Add Steps to the Job Map
        await client.call_tool("add_step", {"job_id": job_id, "name": "Select music", "order": 1})
        await client.call_tool("add_step", {"job_id": job_id, "name": "Play music", "order": 2})

        outcome_match = re.search(r"({.*})", outcome_text, re.DOTALL)
        outcome_data = json.loads(outcome_match.group(1)) if outcome_match else {}

        # Check that opportunity score was calculated correctly: 8.5 + max(8.5 - 4.0, 0) = 8.5 + 4.5 = 13.0
        assert outcome_data.get("opportunity_score") == 13.0

        # 4. Retrieve Data
        job_map_res = await client.call_tool("get_job_map", {"job_id": job_id})
        job_map_text = job_map_res.content[0].text
        job_map_match = re.search(r"(\[.*\])", job_map_text, re.DOTALL)
        job_map_data = json.loads(job_map_match.group(1)) if job_map_match else []

        assert len(job_map_data) == 2
        assert job_map_data[0]["name"] == "Select music"
        assert job_map_data[1]["name"] == "Play music"

        outcomes_res = await client.call_tool("get_outcomes", {"job_id": job_id})
        outcomes_text = outcomes_res.content[0].text
        outcomes_match = re.search(r"(\[.*\])", outcomes_text, re.DOTALL)
        outcomes_data = json.loads(outcomes_match.group(1)) if outcomes_match else []
        assert len(outcomes_data) == 1
        assert (
            outcomes_data[0]["statement"]
            == "Minimize the time it takes to find a specific song when searching the catalog"
        )


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_get_capabilities():
    """Test that the get_capabilities tool returns the generated human-readable summary."""
    async with Client(mcp) as client:
        result = await client.call_tool("get_capabilities", {})
        result_text = result.content[0].text if hasattr(result, "content") else str(result)

        # Check that it returns the generated summary
        assert "Here is what I can help you with" in result_text
        assert "## Read Tools" in result_text
        assert "## Write Tools" in result_text
        assert "## Destructive Tools" in result_text
        # Names every tool including update/delete/compute_opportunity/get_evidence/delete_evidence
        assert "`update_job`" in result_text
        assert "`delete_job`" in result_text
        assert "`compute_opportunity`" in result_text
        assert "`get_evidence`" in result_text
        assert "`delete_evidence`" in result_text
        # Names itself
        assert "`get_capabilities`" in result_text
        assert "`get_capabilities_manifest`" in result_text


@pytest.mark.asyncio
async def test_get_capabilities_manifest_returns_json():
    """Test that get_capabilities_manifest returns the tool manifest as JSON."""
    import json

    async with Client(mcp) as client:
        result = await client.call_tool("get_capabilities_manifest", {})
        result_text = result.content[0].text if hasattr(result, "content") else str(result)

    manifest = json.loads(result_text)
    assert "tools" in manifest
    tool_names = {tool["name"] for tool in manifest["tools"]}
    assert "get_capabilities" in tool_names
    assert "get_capabilities_manifest" in tool_names
    assert "add_job" in tool_names
    assert "delete_job" in tool_names
    # Every tool has required fields
    for tool in manifest["tools"]:
        assert "name" in tool
        assert "summary" in tool
        assert "effect" in tool
        assert "returns" in tool
