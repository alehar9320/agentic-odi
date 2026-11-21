"""MCP coverage for the candidate extraction tools (A4)."""

from __future__ import annotations

import json

import pytest
from agentic_odi_core.remote import error_envelope
from agentic_odi_mcp_server import mcp
from fastmcp import Client
from mcp.types import TextContent

QUOTE = "Setup takes forever when a new hire starts."


def _text(result) -> str:
    content = result.content[0]
    assert isinstance(content, TextContent)
    return content.text


def _json_after_prefix(text: str) -> dict:
    """The tools prefix success messages; take the JSON object that follows."""
    return json.loads(text[text.index("{") :])


async def _quote(client: Client) -> tuple[str, str]:
    await client.call_tool("add_job", {"name": "Onboard"})
    jobs = json.loads(_text(await client.call_tool("get_jobs", {})))
    interview = _json_after_prefix(
        _text(
            await client.call_tool(
                "add_interview",
                {"title": "T", "participant_label": "Ana", "job_id": jobs[0]["id"]},
            )
        )
    )
    quote = _json_after_prefix(
        _text(await client.call_tool("add_quote", {"interview_id": interview["id"], "text": QUOTE}))
    )
    return interview["id"], quote["id"]


async def _job_with_underserved_outcome(client: Client) -> tuple[str, str]:
    """Create a job with an underserved outcome (score > 10). Returns (job_id, outcome_id)."""
    job_result = await client.call_tool("add_job", {"name": "Test Job"})
    job = _json_after_prefix(_text(job_result))
    job_id = job["id"]

    # Create an underserved outcome: importance=9, satisfaction=3 -> score = 9*(10-3) = 63 > 10
    outcome_result = await client.call_tool(
        "add_outcome",
        {
            "job_id": job_id,
            "statement": "Minimize the time to complete the task when onboarding",
            "importance": 9.0,
            "satisfaction": 3.0,
            "claim_check": {"asked": ["How often?", "How satisfied?"], "answers": ["Daily", "Not very"], "skips": []},
        },
    )
    outcome = _json_after_prefix(_text(outcome_result))
    return job_id, outcome["id"]


@pytest.mark.asyncio
async def test_add_solution_requires_underserved_outcome() -> None:
    """add_solution refuses when no outcome is underserved."""
    async with Client(mcp) as client:
        # Create job with only appropriate/overserved outcomes
        job_result = await client.call_tool("add_job", {"name": "Test Job"})
        job = _json_after_prefix(_text(job_result))
        job_id = job["id"]

        # Appropriate outcome (score = 10)
        await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time to complete the task when onboarding",
                "importance": 5.0,
                "satisfaction": 5.0,
                "claim_check": {"asked": ["How often?", "How satisfied?"], "answers": ["Daily", "Moderately"], "skips": []},
            },
        )
        # Overserved outcome (score < 10)
        await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time to complete the task when onboarding",
                "importance": 3.0,
                "satisfaction": 8.0,
                "claim_check": {"asked": ["How often?", "How satisfied?"], "answers": ["Rarely", "Very"], "skips": []},
            },
        )

        outcomes = json.loads(_text(await client.call_tool("get_outcomes", {"job_id": job_id})))

        # Try to add solution - should fail
        result = await client.call_tool(
            "add_solution",
            {
                "title": "Bad Solution",
                "hypothesis": "Won't work",
                "outcome_ids": [o["id"] for o in outcomes],
            },
        )
        payload = json.loads(_text(result))
        assert "error" in payload
        assert "underserved" in payload["error"]["message"].lower()


@pytest.mark.asyncio
async def test_add_solution_succeeds_with_underserved_outcome() -> None:
    """add_solution succeeds when at least one outcome is underserved."""
    async with Client(mcp) as client:
        job_id, outcome_id = await _job_with_underserved_outcome(client)

        result = await client.call_tool(
            "add_solution",
            {
                "title": "Good Solution",
                "hypothesis": "Serves the underserved outcome",
                "outcome_ids": [outcome_id],
            },
        )
        text = _text(result)
        assert text.startswith("Solution created successfully:")
        solution = _json_after_prefix(text)
        assert solution["title"] == "Good Solution"
        assert solution["status"] == "proposed"
        assert solution["outcome_ids"] == [outcome_id]

        # Round-trip via get_candidate (which falls back to repo.get_candidate for solutions)
        fetched = json.loads(_text(await client.call_tool("get_candidate", {"candidate_id": solution["id"]})))
        assert fetched["id"] == solution["id"]
        assert fetched["title"] == "Good Solution"


@pytest.mark.asyncio
async def test_add_solution_rejects_unknown_outcome() -> None:
    """add_solution fails with unknown outcome ID."""
    async with Client(mcp) as client:
        result = await client.call_tool(
            "add_solution",
            {
                "title": "Solution",
                "hypothesis": "Hypothesis",
                "outcome_ids": ["unknown-outcome-id"],
            },
        )
        payload = json.loads(_text(result))
        assert "error" in payload
        assert "not found" in payload["error"]["message"].lower()


@pytest.mark.asyncio
async def test_list_solutions_filters_by_job() -> None:
    """list_solutions with job_id returns only solutions for that job's outcomes."""
    async with Client(mcp) as client:
        # Create two jobs with underserved outcomes
        job1_id, outcome1_id = await _job_with_underserved_outcome(client)
        job2_id, outcome2_id = await _job_with_underserved_outcome(client)

        # Add solutions for each
        sol1 = _json_after_prefix(
            _text(
                await client.call_tool(
                    "add_solution",
                    {"title": "Solution 1", "hypothesis": "H1", "outcome_ids": [outcome1_id]},
                )
            )
        )
        sol2 = _json_after_prefix(
            _text(
                await client.call_tool(
                    "add_solution",
                    {"title": "Solution 2", "hypothesis": "H2", "outcome_ids": [outcome2_id]},
                )
            )
        )

        # List all
        all_sols = json.loads(_text(await client.call_tool("list_solutions", {})))
        assert len(all_sols) == 2

        # Filter by job1
        job1_sols = json.loads(_text(await client.call_tool("list_solutions", {"job_id": job1_id})))
        assert len(job1_sols) == 1
        assert job1_sols[0]["id"] == sol1["id"]

        # Filter by job2
        job2_sols = json.loads(_text(await client.call_tool("list_solutions", {"job_id": job2_id})))
        assert len(job2_sols) == 1
        assert job2_sols[0]["id"] == sol2["id"]


@pytest.mark.asyncio
async def test_update_solution_status_transition() -> None:
    """update_solution persists a status transition and returns updated record."""
    async with Client(mcp) as client:
        job_id, outcome_id = await _job_with_underserved_outcome(client)

        sol = _json_after_prefix(
            _text(
                await client.call_tool(
                    "add_solution",
                    {"title": "Solution", "hypothesis": "H", "outcome_ids": [outcome_id]},
                )
            )
        )

        # Update status
        updated = _json_after_prefix(
            _text(
                await client.call_tool(
                    "update_solution", {"solution_id": sol["id"], "status": "accepted"}
                )
            )
        )
        assert updated["id"] == sol["id"]
        assert updated["status"] == "accepted"

        # Verify via list
        listed = json.loads(_text(await client.call_tool("list_solutions", {})))
        found = next(s for s in listed if s["id"] == sol["id"])
        assert found["status"] == "accepted"


@pytest.mark.asyncio
async def test_update_solution_rejects_unknown_status() -> None:
    """Unknown status string raises ValidationError."""
    async with Client(mcp) as client:
        job_id, outcome_id = await _job_with_underserved_outcome(client)

        sol = _json_after_prefix(
            _text(
                await client.call_tool(
                    "add_solution",
                    {"title": "Solution", "hypothesis": "H", "outcome_ids": [outcome_id]},
                )
            )
        )

        result = await client.call_tool(
            "update_solution", {"solution_id": sol["id"], "status": "invalid_status"}
        )
        payload = json.loads(_text(result))
        assert "unknown candidate status" in payload["error"]["message"].lower()


@pytest.mark.asyncio
async def test_update_solution_rejects_empty_update() -> None:
    """Empty update dict raises ValidationError."""
    async with Client(mcp) as client:
        job_id, outcome_id = await _job_with_underserved_outcome(client)

        sol = _json_after_prefix(
            _text(
                await client.call_tool(
                    "add_solution",
                    {"title": "Solution", "hypothesis": "H", "outcome_ids": [outcome_id]},
                )
            )
        )

        result = await client.call_tool("update_solution", {"solution_id": sol["id"]})
        payload = json.loads(_text(result))
        assert "error" in payload
        assert "at least one field" in payload["error"]["message"].lower()


@pytest.mark.asyncio
async def test_update_solution_reports_not_found() -> None:
    """Updating a missing solution reports not found."""
    async with Client(mcp) as client:
        result = await client.call_tool(
            "update_solution", {"solution_id": "missing-id", "status": "accepted"}
        )
        payload = json.loads(_text(result))
        assert payload["error"]["message"] == "CandidateSolution with ID missing-id not found."


@pytest.mark.asyncio
async def test_extract_then_list_candidates() -> None:
    async with Client(mcp) as client:
        interview_id, quote_id = await _quote(client)
        extracted = json.loads(
            _text(await client.call_tool("extract_candidates", {"quote_id": quote_id}))
        )

        listed = json.loads(
            _text(await client.call_tool("list_candidates", {"interview_id": interview_id}))
        )

    assert extracted
    assert len(listed) == len(extracted)
    assert all(c["quote_id"] == quote_id for c in listed)


@pytest.mark.asyncio
async def test_extract_is_idempotent_over_mcp() -> None:
    async with Client(mcp) as client:
        _, quote_id = await _quote(client)
        await client.call_tool("extract_candidates", {"quote_id": quote_id})
        second = json.loads(
            _text(await client.call_tool("extract_candidates", {"quote_id": quote_id}))
        )

    assert second == []


@pytest.mark.asyncio
async def test_extract_unknown_quote_reports_not_found() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("extract_candidates", {"quote_id": "missing"})
    assert _text(result) == "Error: Quote with ID missing not found."


@pytest.mark.asyncio
async def test_update_candidate_reports_unknown_status() -> None:
    async with Client(mcp) as client:
        _, quote_id = await _quote(client)
        candidates = json.loads(
            _text(await client.call_tool("extract_candidates", {"quote_id": quote_id}))
        )
        result = await client.call_tool(
            "update_candidate", {"candidate_id": candidates[0]["id"], "status": "sideways"}
        )
    payload = json.loads(_text(result))
    assert payload["message"] == "Error: unknown candidate status: sideways"
    assert payload["error"] == error_envelope(ValueError("unknown candidate status: sideways"))


@pytest.mark.asyncio
async def test_get_and_delete_candidate() -> None:
    async with Client(mcp) as client:
        _, quote_id = await _quote(client)
        candidates = json.loads(
            _text(await client.call_tool("extract_candidates", {"quote_id": quote_id}))
        )
        candidate_id = candidates[0]["id"]

        fetched = json.loads(
            _text(await client.call_tool("get_candidate", {"candidate_id": candidate_id}))
        )
        deleted = _text(await client.call_tool("delete_candidate", {"candidate_id": candidate_id}))
        missing = _text(await client.call_tool("get_candidate", {"candidate_id": candidate_id}))

    assert fetched["id"] == candidate_id
    assert deleted == f"Candidate deleted successfully: {candidate_id}"
    payload = json.loads(missing)
    assert payload["error"]["message"] == f"Candidate with ID {candidate_id} not found."


@pytest.mark.asyncio
async def test_list_candidates_rejects_unknown_status() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("list_candidates", {"status": "nope"})
    payload = json.loads(_text(result))
    assert payload["message"] == "Error: unknown candidate status: nope"
    assert payload["error"] == error_envelope(ValueError("unknown candidate status: nope"))
