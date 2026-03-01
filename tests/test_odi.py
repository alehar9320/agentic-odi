import json
import re
import pytest
from fastmcp import Client
from my_server import mcp, jobs_db, steps_db, outcomes_db

@pytest.fixture(autouse=True)
def reset_db():
    """Reset the in-memory databases before each test."""
    jobs_db.clear()
    steps_db.clear()
    outcomes_db.clear()

def extract_id(result_str):
    match = re.search(r'"id"\s*:\s*"([^"]+)"', result_str)
    return match.group(1) if match else None

@pytest.mark.asyncio
async def test_odi_workflow():
    """Test the full ODI workflow (Add Job -> Add Steps -> Add Outcome -> Get Data)."""
    # Use in-memory testing by passing the server instance directly to the client
    async with Client(mcp) as client:
        # 1. Add a Job
        job_result = await client.call_tool("add_job", {"name": "Listen to music", "description": "Listen to music on the go"})
        job_text = job_result.content[0].text
        assert "Job created successfully" in job_text
        
        job_id = extract_id(job_text)
        assert job_id in jobs_db

        # 2. Add Steps to the Job Map
        step1_res = await client.call_tool("add_step", {"job_id": job_id, "name": "Select music", "order": 1})
        step2_res = await client.call_tool("add_step", {"job_id": job_id, "name": "Play music", "order": 2})
        
        step1_text = step1_res.content[0].text
        assert "Step created successfully" in step1_text
        assert "Step created successfully" in step2_res.content[0].text

        step1_id = extract_id(step1_text)

        # 3. Add an Outcome
        outcome_res = await client.call_tool("add_outcome", {
            "job_id": job_id,
            "statement": "Minimize the time it takes to find a specific song",
            "importance": 8.5,
            "satisfaction": 4.0,
            "step_id": step1_id
        })
        outcome_text = outcome_res.content[0].text
        assert "Outcome created successfully" in outcome_text

        outcome_match = re.search(r'({.*})', outcome_text, re.DOTALL)
        outcome_data = json.loads(outcome_match.group(1)) if outcome_match else {}
        
        # Check that opportunity score was calculated correctly: 8.5 + max(8.5 - 4.0, 0) = 8.5 + 4.5 = 13.0
        assert outcome_data.get("opportunity_score") == 13.0

        # 4. Retrieve Data
        job_map_res = await client.call_tool("get_job_map", {"job_id": job_id})
        job_map_text = job_map_res.content[0].text
        job_map_match = re.search(r'(\[.*\])', job_map_text, re.DOTALL)
        job_map_data = json.loads(job_map_match.group(1)) if job_map_match else []
        
        assert len(job_map_data) == 2
        assert job_map_data[0]["name"] == "Select music"
        assert job_map_data[1]["name"] == "Play music"

        outcomes_res = await client.call_tool("get_outcomes", {"job_id": job_id})
        outcomes_text = outcomes_res.content[0].text
        outcomes_match = re.search(r'(\[.*\])', outcomes_text, re.DOTALL)
        outcomes_data = json.loads(outcomes_match.group(1)) if outcomes_match else []
        assert len(outcomes_data) == 1
        assert outcomes_data[0]["statement"] == "Minimize the time it takes to find a specific song"

@pytest.mark.asyncio
async def test_get_capabilities():
    """Test that the get_capabilities tool returns the expected human-readable markdown string."""
    async with Client(mcp) as client:
        result = await client.call_tool("get_capabilities", {})
        result_text = result.content[0].text if hasattr(result, "content") else str(result)
        
        # Check that it returns a string with the expected categories
        assert "Here is what I can help you with" in result_text
        assert "Manage Jobs-to-be-Done (JTBD)" in result_text
        assert "Build Job Maps" in result_text
        assert "Track Desired Outcomes" in result_text
