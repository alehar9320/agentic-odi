"""Branch tests for the streaming tool loop in ``studio.chat``."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

from agentic_odi_studio_api.studio import chat
from agentic_odi_studio_api.studio.connectors import ConnectorService
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
    list_tools_error: Exception | None = None
    tool_result: str = "ok"
    calls: list[tuple[str, dict[str, Any]]] = []

    def __init__(self, url: str) -> None:
        self.url = url

    async def __aenter__(self) -> _Mcp:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def list_tools(self) -> list[Any]:
        if self.list_tools_error is not None:
            raise self.list_tools_error
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
        return self.tool_result


def _chunk(content: str | None = None, tool_calls: list[Any] | None = None) -> Any:
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _collect(request: ChatRequest, service: Any = None, request_id: str | None = None) -> list[str]:
    async def _run() -> list[str]:
        if service is None:
            return [chunk async for chunk in chat.stream_chat(request, request_id=request_id)]
        return [
            chunk
            async for chunk in chat.stream_chat(request, service=service, request_id=request_id)
        ]

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
    _Mcp.list_tools_error = None
    _Mcp.tool_result = "ok"
    monkeypatch.setattr(chat, "check_llm_health", _healthy)
    monkeypatch.setattr(chat, "McpClient", _Mcp)
    monkeypatch.setattr(chat, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(chat, "AsyncOpenAI", lambda **kwargs: _FakeOpenAI(streams, **kwargs))


def _terminal_events(frames: list[str]) -> list[str]:
    """Return the terminal events of a stream, asserting there is exactly one."""
    events = _events(frames)
    terminals = []
    if "message" in events:
        terminals.extend(["message"] * len(events["message"]))
    if "error" in events:
        terminals.extend(["error"] * len(events["error"]))
    assert len(terminals) == 1, f"expected one terminal event, got {terminals}"
    return terminals


def _tool_call(arguments: str, name: str = "get_jobs") -> Any:
    return SimpleNamespace(
        index=0,
        id="call-1",
        function=SimpleNamespace(name=name, arguments=arguments),
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


def test_add_connector_tool_is_advertised() -> None:
    tool = chat.ADD_CONNECTOR_TOOL

    assert tool["type"] == "function"
    assert tool["function"]["name"] == "add_connector"
    assert "preset" in tool["function"]["parameters"]["properties"]


def test_apply_add_connector_registers_and_emits_event(tmp_path) -> None:
    service = ConnectorService(tmp_path / "connectors.json")

    result_str, events = chat._apply_add_connector({"name": "gong", "preset": "gong"}, service)

    assert events[0]["event"] == "connector"
    assert events[0]["data"]["action"] == "registered"
    assert events[0]["data"]["name"] == "gong"
    assert service.list()[0].name == "gong"
    assert "gong" in result_str


def test_apply_add_connector_unknown_preset_emits_error(tmp_path) -> None:
    service = ConnectorService(tmp_path / "connectors.json")

    result_str, events = chat._apply_add_connector({"preset": "nope"}, service)

    assert events[0]["event"] == "connector"
    assert events[0]["data"]["status"] == "error"
    assert service.list() == []


def test_stream_chat_handles_add_connector_locally(monkeypatch, tmp_path) -> None:
    service = ConnectorService(tmp_path / "connectors.json")
    _install(
        monkeypatch,
        [
            _FakeStream(
                [
                    _chunk(
                        tool_calls=[
                            _tool_call('{"name":"gong","preset":"gong"}', name="add_connector")
                        ]
                    )
                ]
            ),
            _FakeStream([_chunk(content="registered it")]),
        ],
    )

    events = _events(_collect(_request(), service=service))

    assert "connector" in events
    registered = json.loads(events["connector"][0])
    assert registered["action"] == "registered"
    assert registered["name"] == "gong"
    assert service.list()[0].name == "gong"
    assert _Mcp.calls == []


def test_stream_chat_add_connector_unknown_preset_emits_error(monkeypatch, tmp_path) -> None:
    service = ConnectorService(tmp_path / "connectors.json")
    _install(
        monkeypatch,
        [
            _FakeStream(
                [_chunk(tool_calls=[_tool_call('{"preset":"nope"}', name="add_connector")])]
            ),
            _FakeStream([_chunk(content="ok")]),
        ],
    )

    events = _events(_collect(_request(), service=service))

    assert json.loads(events["connector"][0])["status"] == "error"
    assert service.list() == []


def test_unreachable_mcp_server_emits_one_error_event(monkeypatch) -> None:
    _install(monkeypatch, [])
    monkeypatch.setattr(chat, "is_endpoint_reachable", lambda url, timeout: False)

    frames = _collect(_request())
    events = _events(frames)

    assert _terminal_events(frames) == ["error"]
    error = json.loads(events["error"][0])["error"]
    assert error["code"] == "mcp_unreachable"
    assert "message" not in events


def test_list_tools_failure_emits_one_error_event(monkeypatch) -> None:
    _install(monkeypatch, [])
    _Mcp.list_tools_error = RuntimeError("mcp died")

    frames = _collect(_request())
    events = _events(frames)

    assert "message" not in events
    error = json.loads(events["error"][0])["error"]
    assert error["code"] == "mcp_unreachable"
    # The reason belongs in the log, not in the client's hands.
    assert "mcp died" not in error["message"]


def test_llm_failure_emits_one_error_event(monkeypatch) -> None:
    class _FailingCompletions:
        async def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("llm exploded")

    class _FailingOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.chat = SimpleNamespace(completions=_FailingCompletions())

    _install(monkeypatch, [])
    monkeypatch.setattr(chat, "AsyncOpenAI", lambda **kwargs: _FailingOpenAI(**kwargs))

    frames = _collect(_request())
    events = _events(frames)

    assert "message" not in events
    error = json.loads(events["error"][0])["error"]
    assert error["code"] == "llm_unreachable"
    assert "llm exploded" not in error["message"]


def test_exhausted_tool_rounds_emit_a_message(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call("{}")])]),
            _FakeStream([_chunk(tool_calls=[_tool_call("{}")])]),
            _FakeStream([_chunk(tool_calls=[_tool_call("{}")])]),
        ],
    )

    frames = _collect(_request())
    events = _events(frames)

    assert _terminal_events(frames) == ["message"]
    message = json.loads(events["message"][0])
    assert "limit of 3 tool rounds" in message["content"]


def test_recoverable_tool_error_is_reported_and_the_round_completes(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call("{}")])]),
            _FakeStream([_chunk("recovered")]),
        ],
    )
    _Mcp.tool_result = "Error: Job with ID JOB-1 not found."

    frames = _collect(_request())
    events = _events(frames)

    tool_event = json.loads(events["tool"][1])
    assert tool_event["status"] == "error"
    assert "not found" in tool_event["preview"]
    assert _terminal_events(frames) == ["message"]


def test_every_event_carries_the_request_id(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call("{}")])]),
            _FakeStream([_chunk("done")]),
        ],
    )

    frames = _collect(_request(), request_id="req-1")
    events = _events(frames)

    assert events
    for name, payloads in events.items():
        for payload in payloads:
            assert json.loads(payload)["request_id"] == "req-1", name


def test_an_unexpected_failure_does_not_leak_internals_to_the_client(monkeypatch) -> None:
    class _ExplodingCompletions:
        async def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("secret internal detail")

    class _ExplodingOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.chat = SimpleNamespace(completions=_ExplodingCompletions())

    _install(monkeypatch, [])
    monkeypatch.setattr(chat, "AsyncOpenAI", lambda **kwargs: _ExplodingOpenAI(**kwargs))

    frames = _collect(_request())
    events = _events(frames)

    error = json.loads(events["error"][0])["error"]
    assert error["code"] == "llm_unreachable"
    assert "secret internal detail" not in json.dumps(error)


def test_a_dead_mcp_server_does_not_leak_internals_to_the_client(monkeypatch) -> None:
    class _DeadMcp(_Mcp):
        async def __aenter__(self) -> _DeadMcp:
            raise RuntimeError("secret mcp detail")

    _install(monkeypatch, [])
    monkeypatch.setattr(chat, "McpClient", _DeadMcp)

    frames = _collect(_request())
    events = _events(frames)

    error = json.loads(events["error"][0])["error"]
    assert error["code"] == "mcp_unreachable"
    assert "secret mcp detail" not in json.dumps(error)
