import json
import re
from uuid import uuid4

import pytest
from fastmcp import Client

from my_server import mcp


def _extract_id(result_text: str) -> str | None:
    match = re.search(r'"id"\s*:\s*"([^"]+)"', result_text)
    return match.group(1) if match else None


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
async def test_get_odi_framework_guidelines_includes_expected_sections():
    async with Client(mcp) as client:
        res = await client.call_tool("get_odi_framework_guidelines", {})
        text = res.content[0].text

        assert "Stage 1: Define Intent" in text
        assert "Stage 2: Capture Desired Outcomes" in text
        assert "Stage 4: Build the Job Map" in text
        # Mention of key tools
        assert "add_job" in text
        assert "add_outcome" in text
        assert "add_step" in text


@pytest.mark.asyncio
async def test_greet_returns_expected_message():
    async with Client(mcp) as client:
        name = "Alex"
        res = await client.call_tool("greet", {"name": name})
        text = res.content[0].text
        assert text == f"Hello, {name}!"

