import ast
import inspect
import json
import re
from uuid import uuid4

import pytest
from agentic_odi_mcp_server import mcp, mcp_server
from fastmcp import Client
from mcp_failures import failure, sentence


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
        assert failure(text).code.value == "not_found"
        assert sentence(text) == f"Error: Job with ID {random_id} not found."


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
        assert failure(text).code.value == "not_found"
        assert sentence(text) == f"Error: Job with ID {random_id} not found."


@pytest.mark.asyncio
async def test_get_job_map_job_not_found_returns_error():
    async with Client(mcp) as client:
        random_id = str(uuid4())
        res = await client.call_tool("get_job_map", {"job_id": random_id})
        text = res.content[0].text
        assert failure(text).code.value == "not_found"
        assert sentence(text) == f"Error: Job with ID {random_id} not found."


@pytest.mark.asyncio
async def test_get_outcomes_job_not_found_returns_error():
    async with Client(mcp) as client:
        random_id = str(uuid4())
        res = await client.call_tool("get_outcomes", {"job_id": random_id})
        text = res.content[0].text
        assert failure(text).code.value == "not_found"
        assert sentence(text) == f"Error: Job with ID {random_id} not found."


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
async def test_add_outcome_description_puts_three_questions_before_the_score():
    #: The docstring below the tool is what the model reads before it decides to
    #: call it, so the interview requirement has to be in it, not only in the gate.
    async with Client(mcp) as client:
        tool = {item.name: item for item in await client.list_tools()}["add_outcome"]

    assert "three questions" in tool.description
    assert "never answer your own question" in tool.description


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
        assert failure(text).code.value == "validation"
        assert sentence(text).startswith("Error:")
        assert "claim_check" in sentence(text)
        assert "ask" in sentence(text).lower()
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
        assert failure(text).code.value == "validation"
        assert sentence(text).startswith("Error: Outcome statement does not match the ODI format")
        assert "Minimize" in sentence(text)


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

        text = result.content[0].text
        assert failure(text).code.value == "out_of_range"
        assert "between 1 and 8" in sentence(text)


def _failure_payload(text: str) -> dict:
    """Read a failing tool's text the way the envelope makes it readable."""
    payload = json.loads(text)
    assert set(payload) == {"error", "message"}, payload
    return payload


@pytest.mark.asyncio
async def test_add_outcome_reports_a_missing_job_with_a_code():
    async with Client(mcp) as client:
        random_id = str(uuid4())
        res = await client.call_tool(
            "add_outcome", {"job_id": random_id, "statement": "Minimize the wait at the counter"}
        )
        payload = _failure_payload(res.content[0].text)

        assert payload["error"]["code"] == "not_found"
        assert payload["error"]["retryable"] is False
        assert payload["message"] == f"Error: Job with ID {random_id} not found."


@pytest.mark.asyncio
async def test_a_refused_score_range_carries_the_range_code():
    async with Client(mcp) as client:
        created = await client.call_tool("add_job", {"name": "Deploy a service"})
        job_id = _extract_id(created.content[0].text)
        assert job_id is not None

        res = await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time to deploy a service",
                "importance": 11.0,
                "satisfaction": 4.0,
                "claim_check": _claim_check(),
            },
        )
        payload = _failure_payload(res.content[0].text)

        assert payload["error"]["code"] == "out_of_range"
        # The score that was out of range is named, so a client can show the
        # message next to the field that needs it instead of on top of the form.
        assert payload["error"]["field"] == "importance"
        assert payload["message"] == "Error: importance must be between 1.0 and 10.0"


@pytest.mark.asyncio
async def test_a_successful_tool_returns_no_envelope():
    async with Client(mcp) as client:
        res = await client.call_tool(
            "add_job", {"name": "Music", "description": "Listen on the go"}
        )

        assert res.content[0].text.startswith("Job created successfully:")


def _is_tool_handler(node: ast.FunctionDef) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Attribute) and decorator.attr == "tool":
            return True
    return False


def _reads_like_a_prose_error(unparsed: str) -> bool:
    text = unparsed.lstrip("fFr").strip("\"'")
    return text.startswith("Error:") or " not found:" in text


def test_no_handler_returns_a_bare_prose_error():
    """A failure that travels as prose is the bug this file exists to keep fixed."""
    tree = ast.parse(inspect.getsource(mcp_server))

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not _is_tool_handler(node):
            continue
        for returned in ast.walk(node):
            if not isinstance(returned, ast.Return) or returned.value is None:
                continue
            unparsed = ast.unparse(returned.value)
            if _reads_like_a_prose_error(unparsed):
                offenders.append(f"mcp_server.py:{returned.lineno} {node.name} -> {unparsed}")

    assert not offenders, "bare prose error returns, which carry no code:\n" + "\n".join(offenders)
