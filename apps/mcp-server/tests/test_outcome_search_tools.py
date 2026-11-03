"""ALH-194 (M2-02.1) — search_outcomes round-trips through the live MCP registry."""

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


async def _seed(client: Client) -> tuple[str, str, str]:
    job = _payload(await client.call_tool("add_job", {"name": "Reconcile supplier invoices"}))
    outcome = _payload(
        await client.call_tool(
            "add_outcome",
            {
                "job_id": job["id"],
                "statement": "Minimize the time it takes to approve an invoice when reconciling",
            },
        )
    )
    theme = _payload(
        await client.call_tool("add_theme", {"name": "Cash timing", "job_id": job["id"]})
    )
    other = _payload(await client.call_tool("add_theme", {"name": "Accuracy", "job_id": job["id"]}))
    await client.call_tool(
        "assign_theme", {"outcome_ids": [outcome["id"]], "theme_id": theme["id"]}
    )
    await client.call_tool(
        "add_evidence",
        {
            "source_name": "interview",
            "source_kind": "transcript",
            "name": "q1",
            "content": "I chase every invoice for days",
            "outcome_id": outcome["id"],
        },
    )
    return str(job["id"]), str(theme["id"]), str(other["id"])


@pytest.mark.asyncio
async def test_search_finds_an_outcome_through_its_evidence_quote() -> None:
    async with Client(mcp) as client:
        job_id, theme_id, other_id = await _seed(client)

        result = _payload(
            await client.call_tool("search_outcomes", {"text": "chase", "job_id": job_id})
        )

        assert result["total"] == 1
        assert result["items"][0]["statement"] == (
            "Minimize the time it takes to approve an invoice when reconciling"
        )


@pytest.mark.asyncio
async def test_the_shared_store_resets_between_tests() -> None:
    """The facet assertions below are exact; they only mean something if no
    theme survives from a previous test in the same session."""
    async with Client(mcp) as client:
        result = _payload(await client.call_tool("search_outcomes", {}))

        assert result["items"] == []
        assert result["facets"]["theme"] == {}


@pytest.mark.asyncio
async def test_search_is_a_read_and_returns_facets_with_the_results() -> None:
    async with Client(mcp) as client:
        job_id, theme_id, other_id = await _seed(client)

        result = _payload(await client.call_tool("search_outcomes", {"job_id": job_id}))

        assert result["facets"]["confidence"] == {"scored": 0, "unscored": 1}
        assert result["facets"]["theme"] == {theme_id: 1, other_id: 0}

        manifest = _payload(await client.call_tool("get_capabilities_manifest", {}))
        tool = next(entry for entry in manifest["tools"] if entry["name"] == "search_outcomes")
        assert tool["effect"] == "read"


@pytest.mark.asyncio
async def test_a_malformed_search_is_refused_with_the_established_error_text() -> None:
    async with Client(mcp) as client:
        job_id, theme_id, other_id = await _seed(client)

        refusal = _payload(
            await client.call_tool("search_outcomes", {"job_id": job_id, "stage": "sidestep"})
        )

        assert refusal["error"]["code"] == "validation"
        assert refusal["message"].startswith("Error:")
        assert "sidestep" in refusal["message"]
