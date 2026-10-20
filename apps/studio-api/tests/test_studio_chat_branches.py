"""Branch tests for the streaming tool loop in ``studio.chat``."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

from agentic_odi_studio_api.studio import chat
from agentic_odi_studio_api.studio.schemas import ChatMessage, ChatRequest


def _request() -> ChatRequest:
    return ChatRequest(
        base_url="http://llm/v1",
        api_key="key",
        model="model",
        mcp_url="http://mcp",
        messages=[ChatMessage(role="user", content="list jobs")],
    )


class _FakeStream:
    def __init__(self, chunks: list[Any]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> Any:
        async def _gen() -> Any:
            for chunk in self._chunks:
                yield chunk

        return _gen()


class _Completions:
    def __init__(self, streams: list[_FakeStream]) -> None:
        self._streams = streams

    async def create(self, **kwargs: Any) -> _FakeStream:
        return self._streams.pop(0)


class _FakeOpenAI:
    def __init__(self, streams: list[_FakeStream], **kwargs: Any) -> None:
        self.chat = SimpleNamespace(completions=_Completions(streams))


class _Mcp:
    error: Exception | None = None
    calls: list[tuple[str, dict[str, Any]]] = []

    def __init__(self, url: str) -> None:
        self.url = url

    async def __aenter__(self) -> _Mcp:
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
        self.calls.append((name, arguments))
        if self.error is not None:
            raise self.error
        return "ok"


def _chunk(content: str | None = None, tool_calls: list[Any] | None = None) -> Any:
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _collect(request: ChatRequest) -> list[str]:
    async def _run() -> list[str]:
        return [chunk async for chunk in chat.stream_chat(request)]

    return asyncio.run(_run())


def _events(frames: list[str]) -> dict[str, list[str]]:
    events: dict[str, list[str]] = {}
    for frame in frames:
        name = None
        data = None
        for line in frame.splitlines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = line[len("data: ") :]
        if name and data is not None:
            events.setdefault(name, []).append(data)
    return events


def _install(monkeypatch, streams: list[_FakeStream]) -> None:
    async def _healthy(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        return True, "ok"

    _Mcp.calls = []
    _Mcp.error = None
    monkeypatch.setattr(chat, "check_llm_health", _healthy)
    monkeypatch.setattr(chat, "McpClient", _Mcp)
    monkeypatch.setattr(chat, "AsyncOpenAI", lambda **kwargs: _FakeOpenAI(streams, **kwargs))


def _tool_call(arguments: str) -> Any:
    return SimpleNamespace(
        index=0,
        id="call-1",
        function=SimpleNamespace(name="get_jobs", arguments=arguments),
    )


def test_stream_chat_falls_back_to_empty_arguments_for_invalid_json(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call("not json")])]),
            _FakeStream([_chunk("done")]),
        ],
    )

    events = _events(_collect(_request()))

    assert _Mcp.calls == [("get_jobs", {})]
    assert json.loads(events["tool"][1])["status"] == "ok"


def test_stream_chat_reports_tool_call_failures(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call("{}")])]),
            _FakeStream([_chunk("recovered")]),
        ],
    )
    _Mcp.error = RuntimeError("tool exploded")

    events = _events(_collect(_request()))

    failure = json.loads(events["tool"][1])
    assert failure["status"] == "error"
    assert "tool exploded" in failure["preview"]
