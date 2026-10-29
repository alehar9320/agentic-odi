"""Tests for the ``render_ui`` local tool in the streaming tool loop."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

from agentic_odi_studio_api.studio import chat
from agentic_odi_studio_api.studio.schemas import ChatMessage, ChatRequest, UiCatalogRequest

CATALOG: dict[str, Any] = {
    "version": 1,
    "components": [
        {
            "type": "outcome-card",
            "kind": "leaf",
            "description": "One desired outcome with its ODI scores.",
            "acceptsChildren": False,
            "props": {
                "type": "object",
                "required": ["id", "statement", "importance", "satisfaction"],
                "properties": {
                    "id": {"type": "string"},
                    "statement": {"type": "string"},
                    "importance": {"type": "number", "minimum": 0, "maximum": 10},
                    "satisfaction": {"type": "number", "minimum": 0, "maximum": 10},
                },
            },
        }
    ],
}

VALID_SPEC: dict[str, Any] = {
    "type": "outcome-card",
    "props": {
        "id": "O-1",
        "statement": "Minimize the time it takes to propagate secrets",
        "importance": 9,
        "satisfaction": 3,
    },
}


def _request(catalog: dict[str, Any] | None = CATALOG) -> ChatRequest:
    return ChatRequest(
        base_url="http://llm/v1",
        api_key="key",
        model="model",
        mcp_url="http://mcp",
        messages=[ChatMessage(role="user", content="score O-1")],
        ui_catalog=UiCatalogRequest(**catalog) if catalog else None,
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
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeStream:
        self.calls.append(kwargs)
        return self._streams.pop(0)


HOLDER: dict[str, _Completions] = {}


class _FakeOpenAI:
    def __init__(self, streams: list[_FakeStream], **kwargs: Any) -> None:
        self.completions = _Completions(streams)
        HOLDER["completions"] = self.completions
        self.chat = SimpleNamespace(completions=self.completions)


class _Mcp:
    def __init__(self, url: str) -> None:
        self.url = url

    async def __aenter__(self) -> _Mcp:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def list_tools(self) -> list[Any]:
        return []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        raise AssertionError("render_ui must never be forwarded to MCP")


def _chunk(content: str | None = None, tool_calls: list[Any] | None = None) -> Any:
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _tool_call(arguments: dict[str, Any]) -> Any:
    return SimpleNamespace(
        index=0,
        id="call-1",
        function=SimpleNamespace(name="render_ui", arguments=json.dumps(arguments)),
    )


def _install(monkeypatch, streams: list[_FakeStream]) -> None:
    async def _healthy(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        return True, "ok"

    HOLDER.clear()
    monkeypatch.setattr(chat, "check_llm_health", _healthy)
    monkeypatch.setattr(chat, "McpClient", _Mcp)
    monkeypatch.setattr(chat, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(chat, "AsyncOpenAI", lambda **kwargs: _FakeOpenAI(streams, **kwargs))


def _collect(request: ChatRequest) -> list[str]:
    async def _run() -> list[str]:
        return [frame async for frame in chat.stream_chat(request)]

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


# ---------------------------------------------------------------------------


def test_render_ui_emits_a_ui_event(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call(VALID_SPEC)])]),
            _FakeStream([_chunk("Build it.")]),
        ],
    )

    events = _events(_collect(_request()))

    assert json.loads(events["ui"][0])["spec"] == VALID_SPEC
    assert json.loads(events["tool"][1])["status"] == "ok"
    assert json.loads(events["message"][-1])["content"] == "Build it."
    assert "canvas_dirty" not in events


def test_render_ui_feeds_a_correction_back_to_the_model(monkeypatch) -> None:
    invalid = {**VALID_SPEC, "props": {**VALID_SPEC["props"], "importance": 40}}
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call(invalid)])]),
            _FakeStream([_chunk("Let me fix that.")]),
        ],
    )

    events = _events(_collect(_request()))
    completions = HOLDER["completions"]

    assert "ui" not in events
    failure = json.loads(events["tool"][1])
    assert failure["status"] == "error"
    assert "importance" in failure["preview"]

    tool_messages = [m for m in completions.calls[1]["messages"] if m["role"] == "tool"]
    assert tool_messages[0]["content"].startswith("UI rejected:")
    assert "Nothing was shown" in tool_messages[0]["content"]


def test_render_ui_is_offered_to_the_model_with_the_catalog(monkeypatch) -> None:
    _install(monkeypatch, [_FakeStream([_chunk("hello")])])

    _collect(_request())

    tools = HOLDER["completions"].calls[0]["tools"]
    assert [tool["function"]["name"] for tool in tools] == [
        "render_ui",
        "remember",
        "add_connector",
    ]
    assert tools[0]["function"]["parameters"]["properties"]["type"]["enum"] == ["outcome-card"]
    assert "outcome-card" in tools[0]["function"]["description"]


def test_api_is_absent_when_the_client_sends_no_catalog(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call(VALID_SPEC)])]),
            _FakeStream([_chunk("Answering in prose.")]),
        ],
    )

    events = _events(_collect(_request(catalog=None)))

    tools = HOLDER["completions"].calls[0]["tools"]
    assert [tool["function"]["name"] for tool in tools] == ["remember", "add_connector"]
    assert "ui" not in events
    assert json.loads(events["tool"][1])["status"] == "error"


def test_prose_before_a_surface_is_kept_and_ordered(monkeypatch) -> None:
    """The sentence that introduces a card is part of the answer, not noise."""
    _install(
        monkeypatch,
        [
            _FakeStream(
                [_chunk("Here is the board. "), _chunk(tool_calls=[_tool_call(VALID_SPEC)])]
            ),
            _FakeStream([_chunk("It is the top bet.")]),
        ],
    )

    events = _events(_collect(_request()))

    names = list(events)
    assert names.index("delta") < names.index("ui")
    assert [json.loads(delta)["text"] for delta in events["delta"]] == [
        "Here is the board. ",
        "It is the top bet.",
    ]
    assert json.loads(events["message"][-1])["content"] == ("Here is the board. It is the top bet.")


def test_plain_reply_streams_each_delta(monkeypatch) -> None:
    _install(monkeypatch, [_FakeStream([_chunk("Just "), _chunk("talking.")])])

    events = _events(_collect(_request()))

    assert [json.loads(delta)["text"] for delta in events["delta"]] == ["Just ", "talking."]
    assert json.loads(events["message"][-1])["content"] == "Just talking."


def _named_tool_call(name: str, arguments: dict[str, Any]) -> Any:
    return SimpleNamespace(
        index=0,
        id="call-1",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def test_remember_proposes_an_observation_the_pm_must_confirm(monkeypatch) -> None:
    from agentic_odi_studio_api.studio.memory import StudioMemory

    memory = StudioMemory(":memory:")
    _install(
        monkeypatch,
        [
            _FakeStream(
                [
                    _chunk(
                        tool_calls=[
                            _named_tool_call(
                                "remember", {"category": "career", "text": "Owns activation."}
                            )
                        ]
                    )
                ]
            ),
            _FakeStream([_chunk("I'll keep that in mind.")]),
        ],
    )

    async def _run() -> list[str]:
        return [frame async for frame in chat.stream_chat(_request(), memory=memory)]

    events = _events(asyncio.run(_run()))

    assert "memory" in events
    payload = json.loads(events["memory"][0])["observation"]
    assert payload["status"] == "proposed"
    assert payload["category"] == "career"
    observations = memory.list_observations()
    assert [item.text for item in observations] == ["Owns activation."]
    assert json.loads(events["message"][-1])["content"] == "I'll keep that in mind."
    memory.close()


def test_an_agent_cannot_confirm_its_own_memory(monkeypatch) -> None:
    """A proposal stays out of the prompt until the person confirms it."""
    from agentic_odi_studio_api.studio.memory import StudioMemory

    memory = StudioMemory(":memory:")
    _install(
        monkeypatch,
        [
            _FakeStream(
                [
                    _chunk(
                        tool_calls=[
                            _named_tool_call(
                                "remember", {"category": "career", "text": "Owns activation."}
                            )
                        ]
                    )
                ]
            ),
            _FakeStream([_chunk("I'll keep that in mind.")]),
        ],
    )

    async def _run() -> list[str]:
        return [frame async for frame in chat.stream_chat(_request(), memory=memory)]

    asyncio.run(_run())

    assert memory.memory_context() == ""
    observation = memory.list_observations()[0]
    memory.update_observation(observation.id, status="confirmed")
    assert "Owns activation." in memory.memory_context()
    memory.close()


def test_remember_rejects_an_unknown_category(monkeypatch) -> None:
    from agentic_odi_studio_api.studio.memory import StudioMemory

    memory = StudioMemory(":memory:")
    _install(
        monkeypatch,
        [
            _FakeStream(
                [_chunk(tool_calls=[_named_tool_call("remember", {"category": "x", "text": "y"})])]
            ),
            _FakeStream([_chunk("Sorry.")]),
        ],
    )

    async def _run() -> list[str]:
        return [frame async for frame in chat.stream_chat(_request(), memory=memory)]

    events = _events(asyncio.run(_run()))

    assert "memory" not in events
    assert any(json.loads(item)["status"] == "error" for item in events["tool"])
    assert memory.list_observations() == []
    memory.close()


def test_remember_without_a_category_is_an_error(monkeypatch) -> None:
    """The old ``kind`` argument must not silently file a fact under ``other``."""
    from agentic_odi_studio_api.studio.memory import StudioMemory

    memory = StudioMemory(":memory:")
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_named_tool_call("remember", {"text": "y"})])]),
            _FakeStream([_chunk("Sorry.")]),
        ],
    )

    async def _run() -> list[str]:
        return [frame async for frame in chat.stream_chat(_request(), memory=memory)]

    events = _events(asyncio.run(_run()))

    assert "memory" not in events
    assert memory.list_observations() == []
    memory.close()
