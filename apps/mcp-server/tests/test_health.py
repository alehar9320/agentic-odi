"""The store health tool reports readiness without touching ODI data."""

from __future__ import annotations

import json

import pytest
from agentic_odi_mcp_server import mcp
from agentic_odi_mcp_server import mcp_server as server
from fastmcp import Client


@pytest.mark.asyncio
async def test_get_health_reports_accessible_store():
    async with Client(mcp) as client:
        res = await client.call_tool("get_health", {})

        payload = json.loads(res.content[0].text)  # type: ignore[index]

    assert payload == {"status": "ok", "store": "accessible"}


@pytest.mark.asyncio
async def test_get_health_reports_degraded_store(monkeypatch):
    monkeypatch.setattr(server._repo, "health", lambda: False)

    async with Client(mcp) as client:
        res = await client.call_tool("get_health", {})

        payload = json.loads(res.content[0].text)  # type: ignore[index]

    assert payload == {"status": "degraded", "store": "locked"}
