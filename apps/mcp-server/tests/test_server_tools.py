import json
import re
from uuid import uuid4

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client


def _extract_id(result_text: str) -> str | None:
    match = re.search(r'"id"\s*:\s*"([^"]+)"', result_text)
    return match.group(1) if match else None


def _claim_check() -> dict:
    """A minimal, honest claim check: a question and the answer it produced."""
    return {
        "asked": ["How often does this happen?"],
        "answers": ["Every week"],
    }


@pytest.mark.asyncio
async def test_get_jobs_lists_created_jobs():
    async with Client(mcp) as client:
        # Create multiple jobs
        job_names = ["Job One", "Job Two"]
        for name in job_names:
            result = await client.call_tool(
                "add_job", {"name": name, "description": f"{name} description"}
            )
            text = result.content[0].text
            assert "Job created successfully" in text

        list_result = await client.call_tool("get_jobs", {})
        list_text = list_result.content[0].text

        # get_jobs returns a JSON array string
        jobs_data = json.loads(list_text)
        assert isinstance(jobs_data, list)
        returned_names = {job["name"] for job in jobs_data}
        assert returned_names == set(job_names)


@pytest.mark.asyncio
async def test_get_job_success_returns_matching_job():
    async with Client(mcp) as client:
        create_res = await client.call_tool(
            "add_job",
            {"name": "Music", "description": "Listen to music on the go"},
        )
        create_text = create_res.content[0].text
        job_id = _extract_id(create_text)
        assert job_id is not None

        get_res = await client.call_tool("get_job", {"job_id": job_id})
        get_text = get_res.content[0].text
        job_data = json.loads(get_text)

        assert job_data["id"] == job_id
        assert job_data["name"] == "Music"
        assert job_data["description"] == "Listen to music on the go"


@pytest.mark.asyncio
async def test_get_job_not_found_returns_error_message():
    async with Client(mcp) as client:
        random_id = str(uuid4())
        res = await client.call_tool("get_job", {"job_id": random_id})
        text = res.content[0].text
        assert text == f"Error: Job with ID {random_id} not found."


@pytest.mark.asyncio
async def test_add_outcome_job_not_found_returns_error():
    async with Client(mcp) as client:
        random_id = str(uuid4())
        res = await client.call_tool(
            "add_outcome",
            {
                "job_id": random_id,
                "statement": "Some outcome",
                "importance": 5.0,
                "satisfaction": 3.0,
            },
        )
        text = res.content[0].text
        assert text == f"Error: Job with ID {random_id} not found."


@pytest.mark.asyncio
async def test_get_job_map_job_not_found_returns_error():
    async with Client(mcp) as client:
        random_id = str(uuid4())
        res = await client.call_tool("get_job_map", {"job_id": random_id})
        text = res.content[0].text
        assert text == f"Error: Job with ID {random_id} not found."


@pytest.mark.asyncio
async def test_get_outcomes_job_not_found_returns_error():
    async with Client(mcp) as client:
        random_id = str(uuid4())
        res = await client.call_tool("get_outcomes", {"job_id": random_id})
        text = res.content[0].text
        assert text == f"Error: Job with ID {random_id} not found."


@pytest.mark.asyncio
async def test_add_outcome_requires_both_scores():
    async with Client(mcp) as client:
        # First create a job
        create_res = await client.call_tool("add_job", {"name": "Job", "description": "Desc"})
        job_id = _extract_id(create_res.content[0].text)
        assert job_id is not None

        # Add an outcome with both scores and the claim check behind them
        outcome_res = await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time it takes to deploy when releasing",
                "importance": 7.0,
                "satisfaction": 3.0,
                "claim_check": _claim_check(),
            },
        )
        outcome_text = outcome_res.content[0].text
        assert "Outcome created successfully" in outcome_text

        match = re.search(r"({.*})", outcome_text, re.DOTALL)
        outcome_data = json.loads(match.group(1)) if match else {}

        # 7.0 + max(7.0 - 3.0, 0) = 11.0
        assert outcome_data.get("opportunity_score") == 11.0


@pytest.mark.asyncio
async def test_add_outcome_refuses_a_score_without_a_claim_check():
    async with Client(mcp) as client:
        create_res = await client.call_tool("add_job", {"name": "Job", "description": "Desc"})
        job_id = _extract_id(create_res.content[0].text)
        assert job_id is not None

        res = await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time it takes to deploy when releasing",
                "importance": 7.0,
                "satisfaction": 3.0,
            },
        )

        text = res.content[0].text
        assert text.startswith("Error:")
        assert "claim_check" in text
        assert "ask" in text.lower()
        # Nothing was written.
        listed = await client.call_tool("get_outcomes", {"job_id": job_id})
        assert json.loads(listed.content[0].text) == []


@pytest.mark.asyncio
async def test_add_outcome_accepts_an_unscored_outcome():
    async with Client(mcp) as client:
        create_res = await client.call_tool("add_job", {"name": "Job", "description": "Desc"})
        job_id = _extract_id(create_res.content[0].text)
        assert job_id is not None

        res = await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time it takes to deploy when releasing",
            },
        )

        assert "Outcome created successfully" in res.content[0].text


@pytest.mark.asyncio
async def test_add_outcome_rejects_a_vague_statement_with_the_fix():
    async with Client(mcp) as client:
        create_res = await client.call_tool("add_job", {"name": "Job", "description": "Desc"})
        job_id = _extract_id(create_res.content[0].text)

        res = await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Make it faster",
                "importance": 8.0,
                "satisfaction": 4.0,
                "claim_check": _claim_check(),
            },
        )

        text = res.content[0].text
        assert text.startswith("Error: Outcome statement does not match the ODI format")
        assert "Minimize" in text


@pytest.mark.asyncio
async def test_get_odi_framework_guidelines_includes_expected_sections():
    async with Client(mcp) as client:
        res = await client.call_tool("get_odi_framework_guidelines", {})
        text = res.content[0].text

        assert "Stage 1: Define Intent" in text
        assert "Stage 2: Capture Desired Outcomes" in text
        assert "Stage 3: Build the Job Map" in text
        # Mention of key tools
        assert "add_job" in text
        assert "add_outcome" in text
        assert "add_step" in text


@pytest.mark.asyncio
async def test_add_step_accepts_the_eight_job_map_stages():
    async with Client(mcp) as client:
        created = await client.call_tool("add_job", {"name": "Deploy a service"})
        job_id = _extract_id(created.content[0].text)
        assert job_id is not None

        await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time to deploy a service when the build is ready",
                "importance": 8.0,
                "satisfaction": 4.0,
                "claim_check": _claim_check(),
            },
        )
        stages = (
            "define",
            "locate",
            "prepare",
            "confirm",
            "execute",
            "monitor",
            "modify",
            "conclude",
        )
        for order, stage in enumerate(stages, start=1):
            result = await client.call_tool(
                "add_step",
                {"job_id": job_id, "name": f"stage {order}", "order": order, "stage": stage},
            )
            assert "Step created successfully" in result.content[0].text

        listed = await client.call_tool("get_job_map", {"job_id": job_id})
        assert [step["order"] for step in json.loads(listed.content[0].text)] == list(range(1, 9))


@pytest.mark.asyncio
async def test_add_step_rejects_an_order_outside_the_job_map():
    async with Client(mcp) as client:
        created = await client.call_tool("add_job", {"name": "Deploy a service"})
        job_id = _extract_id(created.content[0].text)
        assert job_id is not None
        await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time to deploy a service when the build is ready",
                "importance": 8.0,
                "satisfaction": 4.0,
                "claim_check": _claim_check(),
            },
        )

        result = await client.call_tool(
            "add_step", {"job_id": job_id, "name": "stage 9", "order": 9}
        )

        assert result.content[0].text.startswith("Error:")
        assert "between 1 and 8" in result.content[0].text
