"""Tests for MCP hydration and passthrough helpers."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any, cast

import pytest
from agentic_odi_core import ODIService
from agentic_odi_studio_api.studio import mcp_data
from agentic_odi_studio_api.studio.errors import StudioHTTPError
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


def test_fetch_canvas_falls_back_to_seed_when_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: False)

    payload = asyncio.run(mcp_data.fetch_canvas("http://mcp"))

    assert payload["source"] == "seed"
    assert payload["jobs"][0]["id"] == "JOB-402"
    provenance = payload["provenance"]
    assert provenance["kind"] == "seed"
    assert provenance["reason"] == "mcp_unreachable"
    assert provenance["record_counts"] == {
        "jobs": 1,
        "steps": len(payload["steps"]),
        "outcomes": len(payload["outcomes"]),
        "evidence": len(payload["evidence"]),
    }
    assert provenance["generated_at"].endswith("+00:00")


def test_fetch_canvas_marks_a_reachable_but_empty_server_as_empty(monkeypatch) -> None:
    _FakeClient.calls = []
    _FakeClient.error = None
    _FakeClient.payloads = {"get_jobs": "[]"}
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _FakeClient)

    payload = asyncio.run(mcp_data.fetch_canvas("http://mcp"))

    assert payload["source"] == "mcp"
    assert payload["jobs"] == []
    assert payload["provenance"]["kind"] == "empty"
    assert payload["provenance"]["reason"] == "no_jobs"
    assert payload["provenance"]["record_counts"] == {
        "jobs": 0,
        "steps": 0,
        "outcomes": 0,
        "evidence": 0,
    }


def test_fetch_canvas_labels_a_partial_hydration(monkeypatch) -> None:
    class _PartiallyFailingClient(_FakeClient):
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            if name in ("get_job_map", "get_outcomes", "list_evidence"):
                raise RuntimeError("read failed")
            return await super().call_tool(name, arguments)

    _FakeClient.payloads = {"get_jobs": json.dumps([{"id": "job-1"}])}
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _PartiallyFailingClient)

    payload = asyncio.run(mcp_data.fetch_canvas("http://mcp"))

    assert payload["source"] == "mcp"
    assert payload["warnings"]
    assert payload["provenance"]["kind"] == "live"
    assert payload["provenance"]["reason"] == "partial_hydration"


def test_fetch_canvas_hydrates_jobs_steps_and_outcomes(monkeypatch) -> None:
    _FakeClient.calls = []
    _FakeClient.error = None
    _FakeClient.payloads = {
        "get_jobs": json.dumps([{"id": "job-1"}]),
        "get_job_map": json.dumps([{"id": "step-1", "job_id": "job-1"}]),
        "get_outcomes": json.dumps([{"id": "outcome-1", "job_id": "job-1"}]),
        "list_evidence": json.dumps([{"id": "evidence-1", "job_id": "job-1"}]),
    }
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _FakeClient)

    payload = asyncio.run(mcp_data.fetch_canvas("http://mcp"))

    assert payload["jobs"] == [{"id": "job-1"}]
    assert payload["steps"] == [{"id": "step-1", "job_id": "job-1"}]
    assert payload["outcomes"] == [{"id": "outcome-1", "job_id": "job-1"}]
    assert payload["evidence"] == [{"id": "evidence-1", "job_id": "job-1"}]
    assert payload["scheduled_work"] == []
    assert payload["source"] == "mcp"
    assert payload["warnings"] == []
    assert payload["provenance"]["kind"] == "live"
    assert payload["provenance"]["reason"] == "mcp_live"
    assert payload["provenance"]["record_counts"] == {
        "jobs": 1,
        "steps": 1,
        "outcomes": 1,
        "evidence": 1,
    }
    assert _FakeClient.calls == [
        ("get_jobs", {}),
        ("list_scheduled_work", {}),
        ("get_job_map", {"job_id": "job-1"}),
        ("get_outcomes", {"job_id": "job-1"}),
        ("list_evidence", {}),
    ]


def test_fetch_canvas_skips_invalid_json_and_jobs_without_ids(monkeypatch) -> None:
    _FakeClient.calls = []
    _FakeClient.error = None
    _FakeClient.payloads = {"get_jobs": "not json"}
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _FakeClient)

    payload = asyncio.run(mcp_data.fetch_canvas("http://mcp"))

    # A reachable server that returns no usable jobs is genuinely empty; the
    # seed prototype is only a stand-in when the server cannot answer.
    assert payload["source"] == "mcp"
    assert payload["provenance"]["kind"] == "empty"
    assert payload["jobs"] == []

    _FakeClient.payloads = {"get_jobs": json.dumps([{"name": "no id"}])}
    payload = asyncio.run(mcp_data.fetch_canvas("http://mcp"))

    # Entries without an id are skipped, so no per-job lookups happen.
    assert payload["source"] == "mcp"
    assert payload["steps"] == []
    assert payload["outcomes"] == []
    assert _FakeClient.calls == [
        ("get_jobs", {}),
        ("list_scheduled_work", {}),
        ("list_evidence", {}),
        ("get_jobs", {}),
        ("list_scheduled_work", {}),
        ("list_evidence", {}),
    ]


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


class _ResultClient:
    """A client whose ``call_tool`` returns a real ``CallToolResult``.

    ``fastmcp.Client.call_tool`` returns a ``CallToolResult`` object, not a
    string, so ``str(result)`` is its ``repr`` rather than the tool's text. A
    stub that returns a bare string hides that, which is how the canvas could
    hydrate to nothing and silently fall back to seed data.
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


def test_fetch_canvas_hydrates_from_real_tool_results(monkeypatch) -> None:
    """A real ``CallToolResult`` must hydrate the canvas, not fall back to seed."""
    _ResultClient.calls = []
    _ResultClient.error = None
    _ResultClient.payloads = {
        "get_jobs": json.dumps([{"id": "job-1"}]),
        "get_job_map": json.dumps([{"id": "step-1", "job_id": "job-1"}]),
        "get_outcomes": json.dumps([{"id": "outcome-1", "job_id": "job-1"}]),
        "list_evidence": json.dumps([{"id": "evidence-1", "job_id": "job-1"}]),
    }
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _ResultClient)

    payload = asyncio.run(mcp_data.fetch_canvas("http://mcp"))

    assert payload["source"] == "mcp"
    assert payload["jobs"] == [{"id": "job-1"}]
    assert payload["steps"] == [{"id": "step-1", "job_id": "job-1"}]
    assert payload["outcomes"] == [{"id": "outcome-1", "job_id": "job-1"}]
    assert payload["evidence"] == [{"id": "evidence-1", "job_id": "job-1"}]
    assert payload["warnings"] == []


def test_call_mcp_tool_returns_the_text_of_a_real_tool_result(monkeypatch) -> None:
    _ResultClient.calls = []
    _ResultClient.error = None
    _ResultClient.payloads = {"get_jobs": "[]"}
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _ResultClient)

    result = asyncio.run(mcp_data.call_mcp_tool("http://mcp", "get_jobs", {}))

    assert result == "[]"


def test_call_mcp_tool_raises_when_a_real_tool_result_reports_an_error(monkeypatch) -> None:
    """A tool-level failure must not be relayed as a success."""
    _ResultClient.calls = []
    _ResultClient.error = None
    _ResultClient.payloads = {"add_outcome": "Error: Job with ID JOB-402 not found."}
    monkeypatch.setattr(mcp_data, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(mcp_data, "McpClient", _ResultClient)

    with pytest.raises(StudioHTTPError) as exc_info:
        asyncio.run(
            mcp_data.call_mcp_tool(
                "http://mcp", "add_outcome", {"job_id": "JOB-402", "statement": "x"}
            )
        )

    # The tool's own text is classified, so a missing job is a 404, not a 200.
    assert exc_info.value.status_code == 404
    assert exc_info.value.error.code.value == "not_found"
    assert "JOB-402" in exc_info.value.error.message


class _Record:
    def __init__(self, **data: Any) -> None:
        self._data = data

    def model_dump(self) -> dict[str, Any]:
        return dict(self._data)


class _FakeService:
    def __init__(self, jobs: list[_Record]) -> None:
        self._jobs = jobs

    def get_jobs(self) -> list[_Record]:
        return self._jobs

    def get_job_map(self, job_id: str) -> list[_Record]:
        return []

    def get_outcomes(self, job_id: str) -> list[_Record]:
        return []

    def list_evidence(self) -> list[_Record]:
        return []

    def list_scheduled_work(self) -> list[_Record]:
        return []


def test_fetch_local_canvas_is_labelled_live_with_counts() -> None:
    payload = mcp_data.fetch_local_canvas(cast(ODIService, _FakeService([_Record(id="j-1")])))

    assert payload["source"] == "local"
    assert payload["provenance"]["kind"] == "live"
    assert payload["provenance"]["reason"] == "local_store"
    assert payload["provenance"]["record_counts"] == {
        "jobs": 1,
        "steps": 0,
        "outcomes": 0,
        "evidence": 0,
    }


def test_fetch_local_canvas_marks_an_empty_store_as_empty() -> None:
    payload = mcp_data.fetch_local_canvas(cast(ODIService, _FakeService([])))

    assert payload["source"] == "local"
    assert payload["provenance"]["kind"] == "empty"
    assert payload["provenance"]["reason"] == "local_store_empty"
