"""ALH-65 (M2-01) — themes round-trip through the live MCP registry."""

import json
from typing import Any

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client


def _text(result: Any) -> str:
    return result.content[0].text


def _payload(result: Any) -> Any:
    """Tool replies are prose-wrapped JSON; take the first JSON value in the text."""
    text = _text(result)
    start = min((index for index in (text.find("{"), text.find("[")) if index != -1), default=-1)
    assert start != -1, text
    return json.loads(text[start:])


async def _seed_job_with_outcome(client: Client) -> tuple[str, str]:
    job = _payload(await client.call_tool("add_job", {"name": "Reconcile supplier invoices"}))
    outcome = _payload(
        await client.call_tool(
            "add_outcome",
            {
                "job_id": job["id"],
                "statement": (
                    "Minimize the time it takes to find a payment when reconciling invoices"
                ),
            },
        )
    )
    return str(job["id"]), str(outcome["id"])


@pytest.mark.asyncio
async def test_a_theme_tree_builds_files_and_survives_deletion() -> None:
    async with Client(mcp) as client:
        job_id, outcome_id = await _seed_job_with_outcome(client)

        parent = _payload(
            await client.call_tool("add_theme", {"name": "Cash timing", "job_id": job_id})
        )
        child = _payload(
            await client.call_tool(
                "add_theme",
                {"name": "Payment windows", "job_id": job_id, "parent_id": parent["id"]},
            )
        )

        assigned = _payload(
            await client.call_tool(
                "assign_theme", {"outcome_ids": [outcome_id], "theme_id": child["id"]}
            )
        )
        assert assigned[0]["theme_ids"] == [child["id"]]

        renamed = _payload(
            await client.call_tool(
                "rename_theme", {"theme_id": child["id"], "name": "Payment timing"}
            )
        )
        assert renamed["name"] == "Payment timing"

        deleted = _payload(await client.call_tool("delete_theme", {"theme_id": parent["id"]}))
        assert deleted["theme_id"] == parent["id"]

        listed = _payload(await client.call_tool("list_themes", {"job_id": job_id}))
        assert [theme["parent_id"] for theme in listed] == [None]
        surviving = _payload(await client.call_tool("get_outcome", {"outcome_id": outcome_id}))
        assert surviving["theme_ids"] == [child["id"]]


@pytest.mark.asyncio
async def test_a_third_level_theme_is_refused() -> None:
    async with Client(mcp) as client:
        job_id, _ = await _seed_job_with_outcome(client)
        parent = _payload(
            await client.call_tool("add_theme", {"name": "Cash timing", "job_id": job_id})
        )
        child = _payload(
            await client.call_tool(
                "add_theme",
                {"name": "Payment windows", "job_id": job_id, "parent_id": parent["id"]},
            )
        )

        refused = await client.call_tool(
            "add_theme", {"name": "Too deep", "job_id": job_id, "parent_id": child["id"]}
        )

        refusal = _payload(refused)
        assert refusal["error"]["code"] == "validation", refused
        assert refusal["message"].startswith("Error:"), refusal
        assert "two levels" in refusal["message"]


@pytest.mark.asyncio
async def test_a_theme_on_a_foreign_job_is_named_and_refused() -> None:
    async with Client(mcp) as client:
        job_id, outcome_id = await _seed_job_with_outcome(client)
        other = _payload(await client.call_tool("add_job", {"name": "Onboard a new supplier"}))
        foreign = _payload(
            await client.call_tool("add_theme", {"name": "Not yours", "job_id": other["id"]})
        )

        refused = await client.call_tool(
            "assign_theme", {"outcome_ids": [outcome_id], "theme_id": foreign["id"]}
        )

        refusal = _payload(refused)
        assert refusal["error"]["code"] == "validation", refused
        assert refusal["message"].startswith("Error:"), refusal
        assert "workspace theme" in refusal["message"]
        unchanged = _payload(await client.call_tool("get_outcome", {"outcome_id": outcome_id}))
        assert unchanged["theme_ids"] == []
