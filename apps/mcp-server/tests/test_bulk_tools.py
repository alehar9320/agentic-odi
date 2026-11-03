"""ALH-196 (M2-03.1) — bulk changes round-trip through the live MCP registry.

The MCP reply is the same report the terminal prints: a preview that wrote nothing, a token
that takes a row back, and the contract's error text for a request that contradicts itself.
"""

import json
from typing import Any

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client

STATEMENT = "Minimize the time to approve an invoice when reconciling"


def _text(result: Any) -> str:
    return result.content[0].text


def _payload(result: Any) -> Any:
    text = _text(result)
    start = min((index for index in (text.find("{"), text.find("[")) if index != -1), default=-1)
    assert start != -1, text
    return json.loads(text[start:])


async def _seed(client: Client) -> tuple[str, str]:
    job = _payload(await client.call_tool("add_job", {"name": "Reconcile supplier invoices"}))
    outcome = _payload(
        await client.call_tool("add_outcome", {"job_id": job["id"], "statement": STATEMENT})
    )
    theme = _payload(
        await client.call_tool("add_theme", {"name": "Cash timing", "job_id": job["id"]})
    )
    return str(outcome["id"]), str(theme["id"])


@pytest.mark.asyncio
async def test_a_previewed_bulk_writes_nothing_and_offers_no_token() -> None:
    async with Client(mcp) as client:
        outcome_id, theme_id = await _seed(client)

        report = _payload(
            await client.call_tool(
                "bulk_update_outcomes",
                {"outcome_ids": [outcome_id], "add_theme_ids": [theme_id], "dry_run": True},
            )
        )

        assert report["changed"] == [outcome_id]
        assert report["undo_token"] is None
        stored = _payload(await client.call_tool("get_outcome", {"outcome_id": outcome_id}))
        assert stored["theme_ids"] == []


@pytest.mark.asyncio
async def test_undo_returns_the_row_to_the_state_before_the_bulk() -> None:
    async with Client(mcp) as client:
        outcome_id, theme_id = await _seed(client)

        report = _payload(
            await client.call_tool(
                "bulk_update_outcomes", {"outcome_ids": [outcome_id], "add_theme_ids": [theme_id]}
            )
        )

        assert report["undo_token"]
        stored = _payload(await client.call_tool("get_outcome", {"outcome_id": outcome_id}))
        assert stored["theme_ids"] == [theme_id]

        undone = _payload(await client.call_tool("undo_bulk", {"token": report["undo_token"]}))

        assert undone["changed"] == [outcome_id]
        stored = _payload(await client.call_tool("get_outcome", {"outcome_id": outcome_id}))
        assert stored["theme_ids"] == []


@pytest.mark.asyncio
async def test_a_bulk_stage_change_files_the_outcome_on_its_jobs_step() -> None:
    async with Client(mcp) as client:
        job = _payload(await client.call_tool("add_job", {"name": "Reconcile supplier invoices"}))
        step = _payload(
            await client.call_tool(
                "add_step",
                {
                    "job_id": job["id"],
                    "name": "Execute the match",
                    "order": 3,
                    "stage": "execute",
                    "allow_empty_job_map": True,
                },
            )
        )
        outcome = _payload(
            await client.call_tool("add_outcome", {"job_id": job["id"], "statement": STATEMENT})
        )

        report = _payload(
            await client.call_tool(
                "bulk_update_outcomes", {"outcome_ids": [outcome["id"]], "stage": "execute"}
            )
        )

        assert report["changed"] == [outcome["id"]]
        assert report["changes"][0] == {
            "outcome_id": outcome["id"],
            "field": "step_id",
            "from": None,
            "to": step["id"],
        }
        stored = _payload(await client.call_tool("get_outcome", {"outcome_id": outcome["id"]}))
        assert stored["step_id"] == step["id"]


@pytest.mark.asyncio
async def test_an_unknown_stage_refuses_the_whole_call_not_one_row() -> None:
    async with Client(mcp) as client:
        outcome_id, _ = await _seed(client)

        refusal = _payload(
            await client.call_tool(
                "bulk_update_outcomes", {"outcome_ids": [outcome_id], "stage": "sidestep"}
            )
        )

        assert refusal["error"]["code"] == "validation"
        assert refusal["message"].startswith("Error:")
        assert "sidestep" in refusal["message"]


@pytest.mark.asyncio
async def test_a_self_contradicting_theme_change_is_refused_with_the_error_text() -> None:
    async with Client(mcp) as client:
        outcome_id, theme_id = await _seed(client)

        refusal = _payload(
            await client.call_tool(
                "bulk_update_outcomes",
                {
                    "outcome_ids": [outcome_id],
                    "add_theme_ids": [theme_id],
                    "remove_theme_ids": [theme_id],
                },
            )
        )

        assert refusal["error"]["code"] == "validation"
        assert refusal["message"].startswith("Error:")
        assert "both added and removed" in refusal["message"]
