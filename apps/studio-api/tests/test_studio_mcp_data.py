"""Tests for MCP hydration and passthrough helpers."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest
from agentic_odi_studio_api.studio import mcp_data
from agentic_odi_studio_api.studio.errors import StudioHTTPError
from fastapi import HTTPException
from fastmcp.client.client import CallToolResult
from mcp.types import TextContent


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


class _ResultClient:
    """A client whose ``call_tool`` returns a real ``CallToolResult``.

    ``fastmcp.Client.call_tool`` returns a ``CallToolResult`` object, not a
    string, so ``str(result)`` is its ``repr``. Stubbing the client with a plain
    string hid that, which is how the canvas hydration silently fell back to
    seed data in production.
    """

    payloads: dict[str, Any] = {}
    error: Exception | None = None
    calls: list[tuple[str, dict[str, Any]]] = []

    def __init__(self, url: str) -> None:
        self.url = url

    async def __aenter__(self) -> _ResultClient:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        self.calls.append((name, arguments))
        if self.error is not None:
            raise self.error
        text = str(self.payloads.get(name, "[]"))
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            structured_content={"result": text},
            meta=None,
        )


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

    assert "Error calling get_jobs: boom" in exc_info.value.detail


def test_result_text_extracts_the_text_of_a_tool_result() -> None:
    result = CallToolResult(
        content=[TextContent(type="text", text='[{"id": "job-1"}]')],
        structured_content={"result": '[{"id": "job-1"}]'},
        meta=None,
    )

    assert mcp_data.result_text(result) == '[{"id": "job-1"}]'


def test_result_text_passes_through_a_plain_string() -> None:
    assert mcp_data.result_text("already text") == "already text"


def test_fetch_canvas_hydrates_from_real_tool_results(monkeypatch) -> None:
    """A real ``CallToolResult`` must hydrate the canvas, not fall back to seed."""
    _ResultClient.calls = []
    _ResultClient.error = None
    _ResultClient.payloads = {
        "get_jobs": json.dumps([{"id": "job-1"}]),
        "get_job_map": json.dumps([{"id": "step-1", "job_id": "job-1"}]),
        "get_outcomes": json.dumps([{"id": "outcome-1", "job_id": "job-1"}]),
    }
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _ResultClient)

    payload = asyncio.run(mcp_data.fetch_canvas("http://mcp"))

    assert payload["source"] == "mcp"
    assert payload["jobs"] == [{"id": "job-1"}]
    assert payload["steps"] == [{"id": "step-1", "job_id": "job-1"}]
    assert payload["outcomes"] == [{"id": "outcome-1", "job_id": "job-1"}]
    assert payload["warnings"] == []


def test_call_mcp_tool_returns_the_text_of_a_real_tool_result(monkeypatch) -> None:
    _ResultClient.calls = []
    _ResultClient.error = None
    _ResultClient.payloads = {"get_jobs": "[]"}
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _ResultClient)

    result = asyncio.run(mcp_data.call_mcp_tool("http://mcp", "get_jobs", {}))

    assert result == "[]"


def test_call_mcp_tool_raises_when_the_tool_reports_an_error(monkeypatch) -> None:
    """A tool-level failure must not be relayed as a success."""
    _ResultClient.calls = []
    _ResultClient.error = None
    _ResultClient.payloads = {"add_outcome": "Error: Job with ID JOB-402 not found."}
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _ResultClient)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            mcp_data.call_mcp_tool(
                "http://mcp", "add_outcome", {"job_id": "JOB-402", "statement": "x"}
            )
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Error: Job with ID JOB-402 not found."
