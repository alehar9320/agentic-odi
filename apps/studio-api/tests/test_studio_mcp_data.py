"""Tests for MCP hydration and passthrough helpers."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest
from agentic_odi_studio_api.studio import mcp_data
from agentic_odi_studio_api.studio.errors import StudioHTTPError


class _FakeClient:
    payloads: dict[str, Any] = {}
    error: Exception | None = None
    calls: list[tuple[str, dict[str, Any]]] = []

    def __init__(self, url: str) -> None:
        self.url = url

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        if self.error is not None:
            raise self.error
        payload = str(self.payloads.get(name, "[]"))
        # FastMCP hands back a CallToolResult, whose str() is a repr.
        return SimpleNamespace(content=[SimpleNamespace(text=payload)])


def test_fetch_canvas_falls_back_to_seed_when_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: False)

    payload = asyncio.run(mcp_data.fetch_canvas("http://mcp"))

    assert payload["source"] == "seed"
    assert payload["jobs"][0]["id"] == "JOB-402"


def test_fetch_canvas_hydrates_jobs_steps_and_outcomes(monkeypatch) -> None:
    _FakeClient.calls = []
    _FakeClient.error = None
    _FakeClient.payloads = {
        "get_jobs": json.dumps([{"id": "job-1"}]),
        "get_job_map": json.dumps([{"id": "step-1", "job_id": "job-1"}]),
        "get_outcomes": json.dumps([{"id": "outcome-1", "job_id": "job-1"}]),
    }
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _FakeClient)

    payload = asyncio.run(mcp_data.fetch_canvas("http://mcp"))

    assert payload == {
        "jobs": [{"id": "job-1"}],
        "steps": [{"id": "step-1", "job_id": "job-1"}],
        "outcomes": [{"id": "outcome-1", "job_id": "job-1"}],
        "source": "mcp",
        "warnings": [],
    }
    assert _FakeClient.calls == [
        ("get_jobs", {}),
        ("get_job_map", {"job_id": "job-1"}),
        ("get_outcomes", {"job_id": "job-1"}),
    ]


def test_fetch_canvas_skips_invalid_json_and_jobs_without_ids(monkeypatch) -> None:
    _FakeClient.calls = []
    _FakeClient.error = None
    _FakeClient.payloads = {"get_jobs": "not json"}
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _FakeClient)

    payload = asyncio.run(mcp_data.fetch_canvas("http://mcp"))

    assert payload["source"] == "seed"

    _FakeClient.payloads = {"get_jobs": json.dumps([{"name": "no id"}])}
    payload = asyncio.run(mcp_data.fetch_canvas("http://mcp"))

    # Entries without an id are skipped, so no per-job lookups happen.
    assert payload["source"] == "mcp"
    assert payload["steps"] == []
    assert payload["outcomes"] == []
    assert _FakeClient.calls == [("get_jobs", {}), ("get_jobs", {})]


def test_call_mcp_tool_rejects_unreachable_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: False)

    with pytest.raises(StudioHTTPError) as exc_info:
        asyncio.run(mcp_data.call_mcp_tool("http://mcp", "get_jobs", {}))

    assert exc_info.value.status_code == 502
    assert exc_info.value.error.code.value == "mcp_unreachable"
    assert exc_info.value.error.retryable is True
    assert "unreachable" in exc_info.value.error.message.lower()


def test_call_mcp_tool_returns_the_result_text(monkeypatch) -> None:
    _FakeClient.calls = []
    _FakeClient.error = None
    _FakeClient.payloads = {"get_jobs": "[]"}
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _FakeClient)

    result = asyncio.run(mcp_data.call_mcp_tool("http://mcp", "get_jobs", {}))

    assert result == "[]"
    assert _FakeClient.calls == [("get_jobs", {})]


def test_call_mcp_tool_reads_the_text_of_a_call_tool_result(monkeypatch) -> None:
    class _ResultClient(_FakeClient):
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            return SimpleNamespace(
                content=[SimpleNamespace(text='Outcome created successfully: {"id": "O-1"}')]
            )

    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _ResultClient)

    result = asyncio.run(mcp_data.call_mcp_tool("http://mcp", "add_outcome", {}))

    assert result == 'Outcome created successfully: {"id": "O-1"}'


def test_call_mcp_tool_raises_a_typed_error_for_an_error_text(monkeypatch) -> None:
    class _ResultClient(_FakeClient):
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            return SimpleNamespace(
                content=[SimpleNamespace(text="Error: Job with ID JOB-1 not found.")]
            )

    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _ResultClient)

    with pytest.raises(StudioHTTPError) as exc_info:
        asyncio.run(mcp_data.call_mcp_tool("http://mcp", "get_job", {}))

    assert exc_info.value.status_code == 404
    assert exc_info.value.error.code.value == "not_found"


def test_call_mcp_tool_wraps_client_errors(monkeypatch) -> None:
    _FakeClient.calls = []
    _FakeClient.error = RuntimeError("boom")
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _FakeClient)

    with pytest.raises(StudioHTTPError) as exc_info:
        asyncio.run(mcp_data.call_mcp_tool("http://mcp", "get_jobs", {}))

    assert exc_info.value.status_code == 502
    assert exc_info.value.error.code.value == "mcp_unreachable"
    assert exc_info.value.error.retryable is True
    assert "Error calling get_jobs: boom" in exc_info.value.error.message


def test_fetch_canvas_reports_why_the_seed_is_standing_in(monkeypatch) -> None:
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: False)

    payload = asyncio.run(mcp_data.fetch_canvas("http://mcp"))

    assert payload["source"] == "seed"
    assert payload["warnings"] == ["MCP endpoint unreachable"]


def test_call_mcp_tool_reports_a_tool_error_as_a_tool_failure(monkeypatch) -> None:
    from fastmcp.exceptions import ToolError

    class _FailingClient(_FakeClient):
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            raise ToolError("the tool refused")

    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _FailingClient)

    with pytest.raises(StudioHTTPError) as exc_info:
        asyncio.run(mcp_data.call_mcp_tool("http://mcp", "add_job", {}))

    assert exc_info.value.status_code == 500
    assert exc_info.value.error.code.value == "mcp_tool_failed"
