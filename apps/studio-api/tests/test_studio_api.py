"""Tests for the Living Studio sidecar API (``/api/*``)."""

from __future__ import annotations

import json
import socket
from types import SimpleNamespace
from typing import Any

import pytest
from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient

OFFLINE = {
    "base_url": "http://127.0.0.1:1/v1",
    "api_key": "k",
    "model": "m",
    "mcp_url": "http://127.0.0.1:1/mcp",
}


def _client() -> TestClient:
    return TestClient(create_app(InMemoryRepository()))


def _mcp_client() -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend="mcp"))


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
    response = _mcp_client().get("/api/canvas", params={"mcp_url": _closed_url("/mcp")})

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
        ("Give me the ODI Stage-by-Stage guidelines.", "ODI, stage by stage"),
        ("Simulate the impact of an Auto-Sync Agent.", "Simulate the bet by hand"),
        ("Show me the evidence from a customer call.", "Evidence needs a source"),
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


def test_chat_offline_default_points_at_manual_work() -> None:
    events = _stream("/api/chat", _chat_body("hello world"))

    content = json.loads(events["message"][-1])["content"]
    assert "no model is reachable" in content
    assert "/capture" in content
    assert "/help" in content


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
    import agentic_odi_studio_api.studio.chat as chat

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
    monkeypatch.setattr(chat, "is_endpoint_reachable", lambda url, timeout: True)
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
    import agentic_odi_studio_api.studio.chat as chat

    async def _healthy(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        return True, "ok"

    streams = [_FakeStream([_delta_chunk("Just "), _delta_chunk("talking.")])]

    monkeypatch.setattr(chat, "check_llm_health", _healthy)
    monkeypatch.setattr(chat, "McpClient", _FakeMcpClient)
    monkeypatch.setattr(chat, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(chat, "AsyncOpenAI", lambda **kwargs: _FakeOpenAI(streams, **kwargs))

    events = _stream("/api/chat", _chat_body("hi"))

    assert json.loads(events["message"][-1])["content"] == "Just talking."
    assert "canvas_dirty" not in events


# ---------------------------------------------------------------------------
# /api/steps and /api/outcomes (MCP passthrough)
# ---------------------------------------------------------------------------


def test_add_step_surfaces_mcp_failure_as_502() -> None:
    response = _mcp_client().post(
        "/api/steps",
        json={
            "mcp_url": _closed_url("/mcp"),
            "job_id": "JOB-402",
            "name": "9. Ship it",
            "order": 9,
        },
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "mcp_unreachable"


def test_add_outcome_surfaces_mcp_failure_as_502() -> None:
    response = _mcp_client().post(
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
    assert response.json()["error"]["code"] == "mcp_unreachable"


# ---------------------------------------------------------------------------
# /api/canvas, /api/steps, /api/outcomes (local backend)
# ---------------------------------------------------------------------------


def test_canvas_reads_local_repository() -> None:
    repo = InMemoryRepository()
    service = ODIService(repo)
    job = service.add_job(name="Local job", description="Stored locally")
    service.add_outcome(
        job_id=job.id,
        statement="Minimize the time it takes to deploy when releasing",
        importance=8.0,
        satisfaction=3.0,
    )
    service.add_step(job_id=job.id, name="Local step", order=1)
    service.add_evidence(
        source_name="Gong",
        source_kind="mcp",
        name="Call with Ada",
        content="Deploys break whenever a secret rotates.",
        job_id=job.id,
    )

    body = TestClient(create_app(repo)).get("/api/canvas").json()

    assert body["source"] == "local"
    assert body["jobs"][0]["id"] == job.id
    assert body["steps"][0]["name"] == "Local step"
    assert body["outcomes"][0]["statement"] == "Minimize the time it takes to deploy when releasing"
    assert body["evidence"][0]["name"] == "Call with Ada"


def test_promote_evidence_creates_a_scored_outcome() -> None:
    repo = InMemoryRepository()
    service = ODIService(repo)
    job = service.add_job(name="Local job")
    item = service.add_evidence(
        source_name="Gong",
        source_kind="mcp",
        name="Call with Ada",
        content="Third time staging broke after a secret rotation.",
        job_id=job.id,
    )

    response = TestClient(create_app(repo)).post(
        f"/api/evidence/{item.id}/promote",
        json={
            "target": "outcome",
            "job_id": job.id,
            "statement": "Minimize the time it takes to sync a secret across environments when rotating keys",
            "importance": 9,
            "satisfaction": 2,
        },
    )

    assert response.status_code == 200
    outcome = response.json()["result"]
    assert (
        outcome["statement"]
        == "Minimize the time it takes to sync a secret across environments when rotating keys"
    )
    assert outcome["importance"] == 9
    assert outcome["satisfaction"] == 2
    assert outcome["opportunity_score"] == 16


def test_promote_unknown_evidence_is_a_404() -> None:
    repo = InMemoryRepository()
    job = ODIService(repo).add_job(name="Local job")

    response = TestClient(create_app(repo)).post(
        "/api/evidence/missing/promote",
        json={
            "target": "outcome",
            "job_id": job.id,
            "statement": "Minimize the time it takes to sync a secret across environments when rotating keys",
            "importance": 9,
            "satisfaction": 2,
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_post_step_uses_local_service() -> None:
    repo = InMemoryRepository()
    job = ODIService(repo).add_job(name="Local job")
    ODIService(repo).add_outcome(
        job_id=job.id,
        statement="Minimize the time it takes to deploy when releasing",
        importance=8.0,
        satisfaction=3.0,
    )

    response = TestClient(create_app(repo)).post(
        "/api/steps",
        json={"mcp_url": "http://unused", "job_id": job.id, "name": "Ship it", "order": 2},
    )

    assert response.status_code == 200
    assert ODIService(repo).get_job_map(job.id)[0].name == "Ship it"


def test_post_job_rejects_an_invalid_name() -> None:
    response = _client().post("/api/jobs", json={"mcp_url": "http://unused", "name": "Jo"})

    assert response.status_code == 422


def test_post_outcome_uses_local_service() -> None:
    repo = InMemoryRepository()
    job = ODIService(repo).add_job(name="Local job")

    response = TestClient(create_app(repo)).post(
        "/api/outcomes",
        json={
            "mcp_url": "http://unused",
            "job_id": job.id,
            "statement": "Minimize the time to ship a release when the build is green",
            "importance": 9.0,
            "satisfaction": 4.0,
        },
    )

    assert response.status_code == 200
    assert (
        ODIService(repo).get_outcomes(job.id)[0].statement
        == "Minimize the time to ship a release when the build is green"
    )


# ---------------------------------------------------------------------------
# /api/changelog
# ---------------------------------------------------------------------------


def test_get_changelog_returns_parsed_or_fallback_data() -> None:
    response = _client().get("/api/changelog")
    assert response.status_code == 200
    data = response.json()
    assert "releases" in data
    assert len(data["releases"]) > 0
    release = data["releases"][0]
    assert "version" in release
    assert "date" in release
    assert "categories" in release


# ---------------------------------------------------------------------------
# /api/memory and /api/conversations
# ---------------------------------------------------------------------------


def _stream_with(client: TestClient, path: str, payload: dict[str, Any]) -> dict[str, list[str]]:
    with client.stream("POST", path, json=payload) as response:
        assert response.status_code == 200
        return _sse_events("".join(response.iter_text()))


def test_memory_observation_crud() -> None:
    client = _client()

    created = client.post(
        "/api/memory/observations",
        json={"kind": "career", "text": "Owns activation."},
    )
    assert created.status_code == 200
    observation = created.json()["observation"]
    assert observation["status"] == "suggested"

    listed = client.get("/api/memory/observations").json()["observations"]
    assert [item["id"] for item in listed] == [observation["id"]]

    patched = client.patch(
        f"/api/memory/observations/{observation['id']}",
        json={"status": "confirmed", "text": "Owns activation end to end."},
    )
    assert patched.status_code == 200
    assert patched.json()["observation"]["status"] == "confirmed"
    assert patched.json()["observation"]["text"] == "Owns activation end to end."

    assert client.delete(f"/api/memory/observations/{observation['id']}").status_code == 200
    assert client.get("/api/memory/observations").json()["observations"] == []
    assert client.delete(f"/api/memory/observations/{observation['id']}").status_code == 404


def test_memory_rejects_unknown_kind_and_blank_text() -> None:
    client = _client()

    assert (
        client.post("/api/memory/observations", json={"kind": "nonsense", "text": "x"}).status_code
        == 422
    )
    assert (
        client.post("/api/memory/observations", json={"kind": "career", "text": "   "}).status_code
        == 422
    )


def test_pm_authored_context_can_start_confirmed() -> None:
    client = _client()
    response = client.post(
        "/api/memory/observations",
        json={"kind": "opportunity", "text": "Activation is the bet.", "confirmed": True},
    )
    assert response.status_code == 200
    assert response.json()["observation"]["status"] == "confirmed"


def test_conversation_endpoints_and_chat_persistence() -> None:
    client = _client()

    assert client.get("/api/conversations/latest").json() == {
        "conversation": None,
        "turns": [],
    }

    events = _stream_with(client, "/api/chat", _chat_body("hello there"))
    conversation = json.loads(events["conversation"][0])
    assert conversation["id"]
    assert conversation["title"] == "hello there"

    latest = client.get("/api/conversations/latest").json()
    assert latest["conversation"]["id"] == conversation["id"]
    assert [turn["role"] for turn in latest["turns"]] == ["user", "assistant"]


def test_chat_resumes_an_existing_conversation() -> None:
    client = _client()
    created = client.post("/api/conversations").json()["conversation"]

    events = _stream_with(
        client,
        "/api/chat",
        {**_chat_body("second message"), "conversation_id": created["id"]},
    )
    conversation = json.loads(events["conversation"][0])
    assert conversation["id"] == created["id"]
    latest = client.get("/api/conversations/latest").json()
    assert len(latest["turns"]) == 2


def test_clear_memory_removes_conversations_and_observations() -> None:
    client = _client()
    _stream_with(client, "/api/chat", _chat_body("hello"))
    client.post("/api/memory/observations", json={"kind": "career", "text": "Owns activation."})

    assert client.delete("/api/memory").status_code == 200
    assert client.get("/api/conversations/latest").json() == {
        "conversation": None,
        "turns": [],
    }
    assert client.get("/api/memory/observations").json()["observations"] == []
