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


def test_chat_returns_502_when_mcp_is_unreachable_and_the_model_can_answer(monkeypatch) -> None:
    async def _healthy(*args, **kwargs) -> tuple[bool, str]:
        return True, "ok"

    monkeypatch.setattr(router_module.chat_module, "check_llm_health", _healthy)
    monkeypatch.setattr(router_module, "is_endpoint_reachable", lambda *a, **k: False)

    response = TestClient(create_app(InMemoryRepository(), backend="local")).post(
        "/api/chat",
        json={
            "base_url": "http://llm/v1",
            "api_key": "key",
            "model": "model",
            "mcp_url": "http://mcp",
            "messages": [{"role": "user", "content": "list jobs"}],
        },
    )

    assert response.status_code == 502
    assert "unreachable" in response.json()["detail"]


def test_chat_still_streams_guidance_when_the_model_is_offline(monkeypatch) -> None:
    async def _offline(*args, **kwargs) -> tuple[bool, str]:
        return False, "offline"

    monkeypatch.setattr(router_module.chat_module, "check_llm_health", _offline)
    monkeypatch.setattr(router_module, "is_endpoint_reachable", lambda *a, **k: False)

    response = TestClient(create_app(InMemoryRepository(), backend="local")).post(
        "/api/chat",
        json={
            "base_url": "http://llm/v1",
            "api_key": "key",
            "model": "model",
            "mcp_url": "http://mcp",
            "messages": [{"role": "user", "content": "list jobs"}],
        },
    )

    assert response.status_code == 200
    assert "event: status" in response.text
    assert "offline" in response.text
