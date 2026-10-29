"""End-to-end proof: one quote travels the whole spine and survives a reopen.

This is the epic's acceptance test. It walks quote → candidate → outcome →
score → brief → decision → bet → measure through the real MCP tool surface, and
then reopens the store to prove every row was persisted rather than held in
memory. Nothing is stubbed: the store is the real SQLite repository the server
ships, and the extractor is the deterministic fixture the demo uses.

It asserts *numbers* the loop produced (an opportunity score, a decision, a bet)
and that an unmeasured bet reports ``None`` rather than a fabricated zero.
"""

from __future__ import annotations

import json
import os
import re

import pytest

# A file-backed store so the reopen step is meaningful. Set before importing the
# server, which builds its repository at import time from AGENTIC_ODI_DB.
_STORE_PATH = os.environ.setdefault("AGENTIC_ODI_DB", ":memory:")


@pytest.fixture
def server(tmp_path, monkeypatch):
    db = str(tmp_path / "e2e.db")
    monkeypatch.setenv("AGENTIC_ODI_DB", db)
    import importlib

    from agentic_odi_mcp_server import mcp_server

    importlib.reload(mcp_server)
    yield mcp_server, db
    mcp_server.shutdown_store()


def _json_of(payload: str) -> dict:
    """Parse a tool reply, which may prefix a human sentence to the JSON body."""
    match = re.search(r"\{.*\}", payload, re.DOTALL)
    assert match, payload
    parsed = json.loads(match.group(0))
    assert isinstance(parsed, dict)
    return parsed


def _id_of(payload: str) -> str:
    return _json_of(payload)["id"]


@pytest.mark.asyncio
async def test_one_quote_travels_the_whole_spine_and_survives_a_reopen(server) -> None:
    from fastmcp import Client

    mcp_server, db = server

    async with Client(mcp_server.mcp) as client:
        job_id = _id_of(
            (await client.call_tool("add_job", {"name": "Onboard customers"})).content[0].text
        )

        # 1. A quote proposes candidates — nothing is accepted yet.
        candidates = json.loads(
            (
                await client.call_tool(
                    "extract_candidates",
                    {
                        "quote_id": "q-1",
                        "quote": (
                            "Minimize the time it takes to onboard when a customer signs up. "
                            "Minimize the number of setup errors when a customer signs up."
                        ),
                        "job_id": job_id,
                        "job_name": "Onboard customers",
                    },
                )
            )
            .content[0]
            .text
        )
        assert candidates, "the fixture extractor proposed nothing"
        proposed = next(
            (c for c in candidates if c["status"] == "proposed"),
            None,
        )
        assert proposed is not None, [c["status"] for c in candidates]
        proposed_id: str = proposed["id"]

        # Nothing downstream exists yet: a proposal is not an outcome, so the
        # store holds no outcome and the candidate still reads as proposed.
        from agentic_odi_core.factory import build_repository

        before = build_repository(db)
        assert before.get_outcome(proposed_id) is None
        assert before.get_outcomes(job_id) == []
        before.close()
        stored_candidate = _json_of(
            (await client.call_tool("get_candidate", {"candidate_id": proposed_id})).content[0].text
        )
        assert stored_candidate["status"] == "proposed"
        assert stored_candidate["outcome_id"] is None

        # 2. A person accepts one candidate, which becomes exactly one outcome.
        outcome = _json_of(
            (
                await client.call_tool(
                    "accept_candidate",
                    {
                        "candidate_id": proposed_id,
                        "importance": 9.0,
                        "satisfaction": 4.0,
                    },
                )
            )
            .content[0]
            .text
        )
        outcome_id = outcome["id"]
        # 14.0 is computed here, not read back from the production renderer:
        # importance + max(importance - satisfaction, 0) = 9 + max(9 - 4, 0).
        assert outcome["opportunity_score"] == 14.0

        # 3. The score stage reads the outcome back as a sample.
        score = json.loads(
            (await client.call_tool("get_outcome_score", {"outcome_id": outcome_id}))
            .content[0]
            .text
        )
        assert score["opportunity_score"] == 14.0
        assert score["sample_size"] is None  # unknown, not fabricated

        # 4. The brief reports the opportunity with the basis for its figure.
        brief = json.loads(
            (await client.call_tool("get_brief", {"subject_id": outcome_id})).content[0].text
        )
        figures = {figure["name"]: figure for figure in brief["figures"]}
        assert figures["opportunity_score"]["value"] == 14.0
        assert figures["opportunity_score"]["basis"]

        # 5. A person records the decision, with its rationale.
        decision = json.loads(
            (
                await client.call_tool(
                    "record_decision",
                    {
                        "subject_id": outcome_id,
                        "choice": "build",
                        "rationale": "underserved and frequent",
                    },
                )
            )
            .content[0]
            .text
        )
        assert decision["choice"] == "build"

        # 6. The decision carries a bet with the metric that would move.
        bet = json.loads(
            (
                await client.call_tool(
                    "track_bet",
                    {
                        "decision_id": decision["id"],
                        "statement": "activation within a day rises",
                        "metric": "time_to_first_value",
                    },
                )
            )
            .content[0]
            .text
        )

        # 7. Nothing has been measured yet, and the surface says so honestly.
        measurement = json.loads(
            (await client.call_tool("get_measurement", {"bet_id": bet["id"]})).content[0].text
        )
        assert measurement["metric"] == "time_to_first_value"
        assert measurement["value"] is None

    # 8. Every row survived the store being closed and reopened, and the
    #    persisted IDs still connect quote → candidate → outcome → decision → bet.
    from agentic_odi_core.factory import build_repository

    reopened = build_repository(db)
    stored = reopened.get_candidate(proposed_id)
    assert stored is not None
    assert stored.quote_id == "q-1"
    assert stored.status.value == "accepted"
    assert stored.outcome_id == outcome_id
    assert reopened.get_outcome(outcome_id) is not None
    assert reopened.get_decision(decision["id"]) is not None
    assert reopened.get_bet(bet["id"]) is not None
    assert reopened.get_measurement(measurement["bet_id"]) is None  # nothing measured yet
    reopened.close()
