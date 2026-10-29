"""C8/E1 (ALH-39, ALH-46): review a decision and track a bet through MCP.

The MCP surface is a thin adapter over one ``ODIService`` call, so these tests
exercise the tools a model actually reaches: record a decision, re-read it
against today's numbers, and carry a bet through its legal transitions. A
missing measurement stays ``no_evidence``; an illegal transition names the
legal successors.
"""

from __future__ import annotations

import json
import re

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client
from mcp.types import TextContent

_STATEMENT = "Minimize the time it takes to publish a plugin when a release is ready"
_OTHER = "Minimize the cost of supporting a plugin when it ships"


def _text(result) -> str:
    content = result.content[0]
    assert isinstance(content, TextContent)
    return content.text


def _payload(text: str) -> dict:
    match = re.search(r"({.*})", text, re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))


async def _seed(client: Client) -> tuple[str, str]:
    """A job with one chosen outcome and a decision recorded for it.

    ``add_outcome`` snapshots at the real clock, so the score that becomes the
    decision-time baseline is re-recorded at an explicit ``at``. Without that,
    the baseline would be the "now" snapshot and the review could not see the
    decision as being in the past.
    """
    await client.call_tool("add_job", {"name": "Publish a plugin"})
    job_id = json.loads(_text(await client.call_tool("get_jobs", {})))[0]["id"]
    outcome = _payload(
        _text(
            await client.call_tool(
                "add_outcome",
                {
                    "job_id": job_id,
                    "statement": _STATEMENT,
                    "importance": 9.0,
                    "satisfaction": 3.0,
                },
            )
        )
    )
    await client.call_tool(
        "update_outcome",
        {
            "outcome_id": outcome["id"],
            "importance": 9.0,
            "satisfaction": 3.0,
            "at": "2026-01-01T00:00:00Z",
        },
    )
    decision = _payload(
        _text(
            await client.call_tool(
                "record_decision",
                {
                    "job_id": job_id,
                    "chosen_outcome_ids": [outcome["id"]],
                    "rationale": "Publishing speed blocks every release.",
                    "decided_by": "alex",
                    "decided_at": "2026-01-15T00:00:00Z",
                },
            )
        )
    )
    return job_id, decision["id"]


@pytest.mark.asyncio
async def test_review_reports_a_satisfaction_rise() -> None:
    async with Client(mcp) as client:
        job_id, decision_id = await _seed(client)
        outcomes = json.loads(_text(await client.call_tool("get_outcomes", {"job_id": job_id})))
        await client.call_tool(
            "update_outcome",
            {"outcome_id": outcomes[0]["id"], "satisfaction": 5.1},
        )

        review = _payload(
            _text(
                await client.call_tool(
                    "review_decision", {"decision_id": decision_id, "today": "2026-04-01"}
                )
            )
        )
    (only,) = review["outcomes"]
    assert only["state"] == "improved"
    assert only["satisfaction_change"] == pytest.approx(2.1)
    assert review["days_elapsed"] == 76


@pytest.mark.asyncio
async def test_review_refuses_a_malformed_clock() -> None:
    async with Client(mcp) as client:
        _, decision_id = await _seed(client)
        text = _text(
            await client.call_tool("review_decision", {"decision_id": decision_id, "today": "soon"})
        )
    assert text == "Error: today must be an ISO-8601 date"


@pytest.mark.asyncio
async def test_review_reports_an_unknown_decision() -> None:
    async with Client(mcp) as client:
        text = _text(
            await client.call_tool(
                "review_decision", {"decision_id": "nope", "today": "2026-04-01"}
            )
        )
    assert text.startswith("Error: decision not found")


@pytest.mark.asyncio
async def test_outcome_history_and_delta_round_trip() -> None:
    async with Client(mcp) as client:
        job_id, _ = await _seed(client)
        outcome_id = json.loads(_text(await client.call_tool("get_outcomes", {"job_id": job_id})))[
            0
        ]["id"]
        history = json.loads(
            _text(await client.call_tool("get_outcome_history", {"outcome_id": outcome_id}))
        )
        assert len(history) == 2

        await client.call_tool("update_outcome", {"outcome_id": outcome_id, "satisfaction": 5.0})
        delta = _payload(
            _text(await client.call_tool("get_outcome_delta", {"outcome_id": outcome_id}))
        )
    assert delta["satisfaction"] == pytest.approx(2.0)
    assert delta["direction"] == "improved"


@pytest.mark.asyncio
async def test_history_refuses_an_unknown_outcome() -> None:
    async with Client(mcp) as client:
        text = _text(await client.call_tool("get_outcome_history", {"outcome_id": "ghost"}))
    assert text.startswith("Error:")


@pytest.mark.asyncio
async def test_a_bet_keeps_its_baseline_and_advances() -> None:
    async with Client(mcp) as client:
        job_id, decision_id = await _seed(client)
        outcome_id = json.loads(_text(await client.call_tool("get_outcomes", {"job_id": job_id})))[
            0
        ]["id"]
        bet = _payload(
            _text(
                await client.call_tool(
                    "record_bet",
                    {
                        "decision_id": decision_id,
                        "outcome_id": outcome_id,
                        "hypothesis": "Publishing gets under 5 minutes",
                        "target": 6.0,
                        "measure_by": "2026-04-01",
                    },
                )
            )
        )
        captured = bet["baseline"]

        await client.call_tool("update_outcome", {"outcome_id": outcome_id, "satisfaction": 9.0})
        reread = _payload(_text(await client.call_tool("get_bet", {"bet_id": bet["id"]})))
        assert reread["baseline"] == captured

        running = _payload(
            _text(await client.call_tool("advance_bet", {"bet_id": bet["id"], "status": "running"}))
        )
        assert running["status"] == "running"
        measured = _payload(
            _text(
                await client.call_tool("advance_bet", {"bet_id": bet["id"], "status": "measured"})
            )
        )
        assert measured["status"] == "measured"
        assert measured["measured_at"] is not None


@pytest.mark.asyncio
async def test_an_illegal_transition_names_the_legal_ones() -> None:
    async with Client(mcp) as client:
        job_id, decision_id = await _seed(client)
        outcome_id = json.loads(_text(await client.call_tool("get_outcomes", {"job_id": job_id})))[
            0
        ]["id"]
        bet = _payload(
            _text(
                await client.call_tool(
                    "record_bet",
                    {
                        "decision_id": decision_id,
                        "outcome_id": outcome_id,
                        "hypothesis": "h",
                        "target": 6.0,
                        "measure_by": "2026-04-01",
                    },
                )
            )
        )
        text = _text(
            await client.call_tool("advance_bet", {"bet_id": bet["id"], "status": "measured"})
        )
    assert text.startswith("Error:")
    assert "running" in text and "abandoned" in text


@pytest.mark.asyncio
async def test_bets_list_and_refusals() -> None:
    async with Client(mcp) as client:
        job_id, decision_id = await _seed(client)
        outcome_id = json.loads(_text(await client.call_tool("get_outcomes", {"job_id": job_id})))[
            0
        ]["id"]
        await client.call_tool(
            "record_bet",
            {
                "decision_id": decision_id,
                "outcome_id": outcome_id,
                "hypothesis": "h",
                "target": 6.0,
                "measure_by": "2026-04-01",
            },
        )
        listed = json.loads(_text(await client.call_tool("list_bets", {"job_id": job_id})))
        assert len(listed) == 1

        assert _text(await client.call_tool("get_bet", {"bet_id": "nope"})).startswith("Error:")
        assert _text(
            await client.call_tool("advance_bet", {"bet_id": "nope", "status": "running"})
        ).startswith("Error:")
        assert _text(
            await client.call_tool(
                "record_bet",
                {
                    "decision_id": "nope",
                    "outcome_id": outcome_id,
                    "hypothesis": "h",
                    "target": 6.0,
                    "measure_by": "2026-04-01",
                },
            )
        ).startswith("Error: decision not found")
        assert _text(
            await client.call_tool(
                "record_bet",
                {
                    "decision_id": decision_id,
                    "outcome_id": "ghost",
                    "hypothesis": "h",
                    "target": 6.0,
                    "measure_by": "2026-04-01",
                },
            )
        ).startswith("Error:")
