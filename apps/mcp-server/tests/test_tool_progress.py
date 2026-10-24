"""Long tools report progress so the Studio can stop looking hung."""

from __future__ import annotations

import json

import pytest
from agentic_odi_mcp_server.mcp_server import mcp
from fastmcp import Client


async def _collect_progress(client: Client, tool: str, arguments: dict) -> tuple[object, list]:
    events: list[tuple[float, float | None, str | None]] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        events.append((progress, total, message))

    result = await client.call_tool(tool, arguments, progress_handler=on_progress)
    return result, events


@pytest.mark.asyncio
async def test_evaluate_outcome_reports_progress_before_returning() -> None:
    async with Client(mcp) as client:
        result, events = await _collect_progress(
            client,
            "evaluate_outcome",
            {"statement": "Minimize the time to ship when the build is green"},
        )

    assert json.loads(result.content[0].text)["valid"] is True  # type: ignore[index]
    assert events
    assert events[-1][0] == events[-1][1]
    assert events[-1][2] == "Evaluation complete"


@pytest.mark.asyncio
async def test_add_evidence_reports_progress_before_returning() -> None:
    async with Client(mcp) as client:
        result, events = await _collect_progress(
            client,
            "add_evidence",
            {
                "source_name": "gong",
                "source_kind": "mcp",
                "name": "quote",
                "content": "The setup took two hours.",
            },
        )

    assert "Evidence created successfully" in result.content[0].text  # type: ignore[index]
    assert events
    assert events[-1][0] == events[-1][1]
    assert events[-1][2] == "Evidence stored"
