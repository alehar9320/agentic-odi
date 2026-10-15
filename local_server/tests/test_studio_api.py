"""Tests for the Living Studio sidecar API (``/api/*``)."""

from __future__ import annotations

import json
import socket
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from local_server.app import create_app

OFFLINE = {
    "base_url": "http://127.0.0.1:1/v1",
    "api_key": "k",
    "model": "m",
    "mcp_url": "http://127.0.0.1:1/mcp",
}


def _client() -> TestClient:
    return TestClient(create_app())


def _closed_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _closed_url(path: str) -> str:
    return f"http://127.0.0.1:{_closed_port()}{path}"


class _ListeningSocket:
    def __init__(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port: int = self._sock.getsockname()[1]

    def url(self, path: str = "/mcp") -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def close(self) -> None:
        self._sock.close()


def _sse_events(body: str) -> dict[str, list[str]]:
    events: dict[str, list[str]] = {}
    for block in body.split("\n\n"):
        name = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = line[len("data: ") :]
        if name and data is not None:
            events.setdefault(name, []).append(data)
    return events


def _chat_body(user_input: str, messages: list[dict[str, str]] | None = None) -> dict[str, Any]:
    history = list(messages or [])
    history.append({"role": "user", "content": user_input})
    return {**OFFLINE, "messages": history}


def _stream(path: str, payload: dict[str, Any]) -> dict[str, list[str]]:
    with _client().stream("POST", path, json=payload) as response:
        assert response.status_code == 200
        return _sse_events("".join(response.iter_text()))


# ---------------------------------------------------------------------------
# /api/config
# ---------------------------------------------------------------------------


def test_config_returns_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_BASE_URL", "http://llm:9999/v1")
    monkeypatch.setenv("AGENTIC_ODI_API_KEY", "secret-key")
    monkeypatch.setenv("AGENTIC_ODI_MODEL", "my-model")
    monkeypatch.setenv("AGENTIC_ODI_MCP_URL", "http://mcp:9999/mcp")

    response = _client().get("/api/config")

    assert response.status_code == 200
    assert response.json()["defaults"] == {
        "base_url": "http://llm:9999/v1",
        "api_key": "secret-key",
        "model_name": "my-model",
        "mcp_url": "http://mcp:9999/mcp",
    }


def test_config_uses_streamlit_compatible_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "AGENTIC_ODI_BASE_URL",
        "AGENTIC_ODI_API_KEY",
        "AGENTIC_ODI_MODEL",
        "AGENTIC_ODI_MCP_URL",
    ):
        monkeypatch.delenv(var, raising=False)

    defaults = _client().get("/api/config").json()["defaults"]

    assert defaults == {
        "base_url": "http://localhost:8001/v1",
        "api_key": "local",
        "model_name": "local-tools-model",
        "mcp_url": "http://localhost:8000/mcp",
    }


# ---------------------------------------------------------------------------
# /api/health/*
# ---------------------------------------------------------------------------


def test_mcp_health_unreachable() -> None:
    response = _client().post("/api/health/mcp", json={"mcp_url": _closed_url("/mcp")})

    assert response.status_code == 200
    assert response.json() == {"reachable": False}


def test_mcp_health_reachable() -> None:
    server = _ListeningSocket()
    try:
        response = _client().post("/api/health/mcp", json={"mcp_url": server.url()})
        assert response.json() == {"reachable": True}
    finally:
        server.close()


def test_llm_health_offline() -> None:
    response = _client().post(
        "/api/health/llm",
        json={"base_url": _closed_url("/v1"), "api_key": "k", "model": "m"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["healthy"] is False
    assert body["message"] == "LLM server offline (Local Studio Mode enabled)"


# ---------------------------------------------------------------------------
# /api/canvas
# ---------------------------------------------------------------------------


def test_canvas_falls_back_to_seed_when_mcp_unreachable() -> None:
    response = _client().get("/api/canvas", params={"mcp_url": _closed_url("/mcp")})

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "seed"
    assert body["jobs"][0]["id"] == "JOB-402"
    assert len(body["steps"]) == 8
    assert len(body["outcomes"]) == 3
    assert body["outcomes"][0]["id"] == "O-1"
    assert body["outcomes"][0]["opportunity_score"] == 15.3
    assert body["outcomes"][0]["evidence"].startswith("Customer Call #104")


# ---------------------------------------------------------------------------
# /api/chat (SSE)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("Give me the ODI Stage-by-Stage guidelines.", "Stage 1"),
        ("Simulate the impact of an Auto-Sync Agent.", "WYSIWYG Impact Simulation Result"),
        ("Show me the evidence from a customer call.", "Causal Lineage"),
    ],
)
def test_chat_offline_fallbacks_stream_deltas_and_message(prompt: str, expected: str) -> None:
    events = _stream("/api/chat", _chat_body(prompt))

    assert "delta" in events
    assert "message" in events
    content = json.loads(events["message"][-1])["content"]
    assert expected in content
    streamed = "".join(json.loads(d)["text"] for d in events["delta"])
    assert streamed == content


def test_chat_offline_default_echoes_intent() -> None:
    events = _stream("/api/chat", _chat_body("hello world"))

    content = json.loads(events["message"][-1])["content"]
    assert '"hello world"' in content
    assert "Opportunity Score of 15.3" in content


def _delta_chunk(content: str | None = None, tool_calls: list[Any] | None = None) -> Any:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=tool_calls),
            )
        ]
    )


class _FakeStream:
    def __init__(self, chunks: list[Any]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> Any:
        async def _gen() -> Any:
            for chunk in self._chunks:
                yield chunk

        return _gen()


class _FakeCompletions:
    def __init__(self, streams: list[_FakeStream]) -> None:
        self._streams = streams
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeStream:
        self.calls.append(kwargs)
        return self._streams.pop(0)


class _FakeOpenAI:
    def __init__(self, streams: list[_FakeStream], **kwargs: Any) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions(streams))


class _FakeMcpClient:
    calls: list[tuple[str, dict[str, Any]]] = []

    def __init__(self, url: str) -> None:
        self.url = url

    async def __aenter__(self) -> _FakeMcpClient:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def list_tools(self) -> list[Any]:
        return [
            SimpleNamespace(
                name="get_jobs",
                description="List jobs",
                input_schema={"type": "object", "properties": {}},
            )
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        _FakeMcpClient.calls.append((name, arguments))
        return '[{"id": "JOB-402"}]'


def test_chat_live_tool_loop_emits_tool_and_final_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import local_server.studio.chat as chat

    async def _healthy(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        return True, "ok"

    tool_delta = SimpleNamespace(
        index=0,
        id="call_1",
        function=SimpleNamespace(name="get_jobs", arguments="{}"),
    )
    streams = [
        _FakeStream([_delta_chunk(tool_calls=[tool_delta])]),
        _FakeStream([_delta_chunk("Listing "), _delta_chunk("jobs now.")]),
    ]
    _FakeMcpClient.calls = []

    monkeypatch.setattr(chat, "check_llm_health", _healthy)
    monkeypatch.setattr(chat, "McpClient", _FakeMcpClient)
    monkeypatch.setattr(chat, "AsyncOpenAI", lambda **kwargs: _FakeOpenAI(streams, **kwargs))

    events = _stream("/api/chat", _chat_body("list the jobs"))

    assert "tool" in events
    assert json.loads(events["tool"][0])["name"] == "get_jobs"
    assert json.loads(events["message"][-1])["content"] == "Listing jobs now."
    assert "canvas_dirty" in events
    assert json.loads(events["canvas_dirty"][-1])["value"] is True
    assert _FakeMcpClient.calls == [("get_jobs", {})]


def test_chat_live_without_tools_streams_plain_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import local_server.studio.chat as chat

    async def _healthy(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        return True, "ok"

    streams = [_FakeStream([_delta_chunk("Just "), _delta_chunk("talking.")])]

    monkeypatch.setattr(chat, "check_llm_health", _healthy)
    monkeypatch.setattr(chat, "McpClient", _FakeMcpClient)
    monkeypatch.setattr(chat, "AsyncOpenAI", lambda **kwargs: _FakeOpenAI(streams, **kwargs))

    events = _stream("/api/chat", _chat_body("hi"))

    assert json.loads(events["message"][-1])["content"] == "Just talking."
    assert "canvas_dirty" not in events


# ---------------------------------------------------------------------------
# /api/steps and /api/outcomes (MCP passthrough)
# ---------------------------------------------------------------------------


def test_add_step_surfaces_mcp_failure_as_502() -> None:
    response = _client().post(
        "/api/steps",
        json={
            "mcp_url": _closed_url("/mcp"),
            "job_id": "JOB-402",
            "name": "9. Ship it",
            "order": 9,
        },
    )

    assert response.status_code == 502
    assert "detail" in response.json()


def test_add_outcome_surfaces_mcp_failure_as_502() -> None:
    response = _client().post(
        "/api/outcomes",
        json={
            "mcp_url": _closed_url("/mcp"),
            "job_id": "JOB-402",
            "statement": "Minimize the time to ship",
            "importance": 8.5,
            "satisfaction": 3.5,
        },
    )

    assert response.status_code == 502
    assert "detail" in response.json()
