"""Tests for successful passthrough responses from the Studio router."""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import router as router_module
from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend="mcp"))


def test_post_step_returns_the_mcp_result(monkeypatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((mcp_url, tool, arguments))
        return "step-1"

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)

    response = _client().post(
        "/api/steps",
        json={"mcp_url": "http://mcp", "job_id": "job-1", "name": "Execute", "order": 5},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "result": "step-1"}
    assert calls == [("http://mcp", "add_step", {"job_id": "job-1", "name": "Execute", "order": 5})]


def test_post_outcome_returns_the_mcp_result(monkeypatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((mcp_url, tool, arguments))
        return "outcome-1"

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)

    response = _client().post(
        "/api/outcomes",
        json={
            "mcp_url": "http://mcp",
            "job_id": "job-1",
            "statement": "Minimize the time to ship",
            "importance": 8.5,
            "satisfaction": 3.5,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "result": "outcome-1"}
    assert calls == [
        (
            "http://mcp",
            "add_outcome",
            {
                "job_id": "job-1",
                "statement": "Minimize the time to ship",
                "importance": 8.5,
                "satisfaction": 3.5,
            },
        )
    ]
