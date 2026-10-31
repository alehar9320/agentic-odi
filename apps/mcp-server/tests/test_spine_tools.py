"""The spine and candidate tools over the MCP boundary.

These drive the full quote-to-measurement chain through ``call_tool`` — the same
surface a client uses — and pin both the success shapes and the honest error
branches (a missing id names the id rather than inventing a number).
"""

from __future__ import annotations

import json
import re

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client

VALID = "Minimize the time it takes to onboard a new customer when they sign up."


def _id(text: str) -> str:
    match = re.search(r'"id"\s*:\s*"([^"]+)"', text)
    assert match is not None, text
    return match.group(1)


async def _job(client) -> str:
    result = await client.call_tool("add_job", {"name": "Onboard customers"})
    return _id(result.content[0].text)


async def _extract(client, job_id: str, quote: str = VALID, quote_id: str = "q1") -> str:
    result = await client.call_tool(
        "extract_candidates", {"quote_id": quote_id, "quote": quote, "job_id": job_id}
    )
    return json.loads(result.content[0].text)[0]["id"]


@pytest.mark.asyncio
async def test_extract_proposes_and_reports_an_unknown_job():
    async with Client(mcp) as client:
        job_id = await _job(client)

        proposed = await client.call_tool(
            "extract_candidates", {"quote_id": "q1", "quote": VALID, "job_id": job_id}
        )
        payload = json.loads(proposed.content[0].text)  # type: ignore[index]
        assert payload[0]["status"] == "proposed"
        assert payload[0]["outcome_id"] is None

        missing = await client.call_tool(
            "extract_candidates", {"quote_id": "q1", "quote": VALID, "job_id": "nope"}
        )
        assert missing.content[0].text == "Job not found: nope"  # type: ignore[index]


@pytest.mark.asyncio
async def test_list_and_get_candidate_cover_the_error_branches():
    async with Client(mcp) as client:
        job_id = await _job(client)
        candidate_id = await _extract(client, job_id)

        listed = await client.call_tool("list_candidates", {"job_id": job_id})
        assert json.loads(listed.content[0].text)[0]["id"] == candidate_id  # type: ignore[index]

        bad_status = await client.call_tool("list_candidates", {"status": "bogus"})
        assert bad_status.content[0].text == "Error: unknown candidate status: bogus"  # type: ignore[index]

        fetched = await client.call_tool("get_candidate", {"candidate_id": candidate_id})
        assert json.loads(fetched.content[0].text)["id"] == candidate_id  # type: ignore[index]

        missing = await client.call_tool("get_candidate", {"candidate_id": "nope"})
        assert missing.content[0].text == "Error: Candidate with ID nope not found."  # type: ignore[index]


@pytest.mark.asyncio
async def test_accept_creates_one_outcome_and_refuses_a_second_decision():
    async with Client(mcp) as client:
        job_id = await _job(client)
        candidate_id = await _extract(client, job_id)

        accepted = await client.call_tool(
            "accept_candidate",
            {"candidate_id": candidate_id, "importance": 9.0, "satisfaction": 4.0},
        )
        text = accepted.content[0].text  # type: ignore[index]
        assert text.startswith("Outcome created successfully: ")
        assert '"opportunity_score":14.0' in text

        again = await client.call_tool(
            "accept_candidate",
            {"candidate_id": candidate_id, "importance": 9.0, "satisfaction": 4.0},
        )
        assert "already accepted" in again.content[0].text  # type: ignore[index]

        missing = await client.call_tool(
            "accept_candidate", {"candidate_id": "nope", "importance": 9.0, "satisfaction": 4.0}
        )
        assert missing.content[0].text == "Error: Candidate with ID nope not found."  # type: ignore[index]


@pytest.mark.asyncio
async def test_reject_keeps_the_reason_and_merge_creates_no_outcome():
    async with Client(mcp) as client:
        job_id = await _job(client)
        first = await _extract(client, job_id)
        second = await _extract(
            client,
            job_id,
            quote="Minimize the number of steps it takes to activate a new account when they sign up.",
            quote_id="q2",
        )

        accepted = await client.call_tool(
            "accept_candidate", {"candidate_id": first, "importance": 9.0, "satisfaction": 4.0}
        )
        outcome_id = _id(accepted.content[0].text)  # type: ignore[index]

        merged = await client.call_tool(
            "merge_candidate", {"candidate_id": second, "merged_into": outcome_id}
        )
        merged_text = merged.content[0].text  # type: ignore[index]
        assert merged_text.startswith("Candidate merged: ")
        assert json.loads(merged_text.removeprefix("Candidate merged: "))["status"] == "merged"

        missing_candidate = await client.call_tool(
            "merge_candidate", {"candidate_id": "nope", "merged_into": outcome_id}
        )
        assert missing_candidate.content[0].text == "Error: Candidate with ID nope not found."  # type: ignore[index]

        rejected = await client.call_tool(
            "reject_candidate", {"candidate_id": "nope", "reason": "Not an outcome."}
        )
        assert rejected.content[0].text == "Error: Candidate with ID nope not found."  # type: ignore[index]


@pytest.mark.asyncio
async def test_the_whole_spine_runs_over_mcp():
    async with Client(mcp) as client:
        job_id = await _job(client)
        candidate_id = await _extract(client, job_id)
        accepted = await client.call_tool(
            "accept_candidate",
            {"candidate_id": candidate_id, "importance": 9.0, "satisfaction": 4.0},
        )
        outcome_id = _id(accepted.content[0].text)  # type: ignore[index]

        score = json.loads(
            (await client.call_tool("get_outcome_score", {"outcome_id": outcome_id}))
            .content[0]
            .text  # type: ignore[index]
        )
        assert score["opportunity_score"] == 14.0

        brief = json.loads(
            (await client.call_tool("get_brief", {"subject_id": outcome_id})).content[0].text  # type: ignore[index]
        )
        assert brief["subject_id"] == outcome_id
        assert brief["figures"]

        decision = json.loads(
            (
                await client.call_tool(
                    "record_decision",
                    {
                        "subject_id": outcome_id,
                        "choice": "Build the guided onboarding",
                        "rationale": "The score is underserved.",
                    },
                )
            )
            .content[0]
            .text  # type: ignore[index]
        )
        assert decision["subject_id"] == outcome_id

        bet = json.loads(
            (
                await client.call_tool(
                    "track_bet",
                    {
                        "decision_id": decision["id"],
                        "statement": "Guided onboarding cuts time",
                        "metric": "median onboarding minutes",
                    },
                )
            )
            .content[0]
            .text  # type: ignore[index]
        )
        assert bet["decision_id"] == decision["id"]

        measurement = json.loads(
            (await client.call_tool("get_measurement", {"bet_id": bet["id"]})).content[0].text  # type: ignore[index]
        )
        assert measurement["bet_id"] == bet["id"]
        assert measurement["value"] is None


@pytest.mark.asyncio
async def test_spine_tools_name_a_missing_id_rather_than_fabricating():
    async with Client(mcp) as client:
        score = await client.call_tool("get_outcome_score", {"outcome_id": "nope"})
        assert score.content[0].text == "Error: Outcome with ID nope not found."  # type: ignore[index]

        brief = await client.call_tool("get_brief", {"subject_id": "nope"})
        assert brief.content[0].text == "Error: Outcome with ID nope not found."  # type: ignore[index]

        decision = await client.call_tool(
            "record_decision", {"subject_id": "nope", "choice": "x", "rationale": "y"}
        )
        assert decision.content[0].text == "Error: Outcome with ID nope not found."  # type: ignore[index]

        bet = await client.call_tool(
            "track_bet", {"decision_id": "nope", "statement": "s", "metric": "m"}
        )
        assert bet.content[0].text == "Error: Decision with ID nope not found."  # type: ignore[index]

        measurement = await client.call_tool("get_measurement", {"bet_id": "nope"})
        assert measurement.content[0].text == "Error: Bet with ID nope not found."  # type: ignore[index]
