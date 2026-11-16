"""The Studio's two-turn score gate: ``prepare_score`` before any scored write.

These cover the chat-loop half of issue #341. A model that calls ``add_outcome``
with a number before a person has answered must produce no outcome, end with a
score plan on the stream, and — once the plan resolves — have only the plan's
basis written, never a ``claim_check`` the model supplied.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

from agentic_odi_studio_api.studio import chat
from agentic_odi_studio_api.studio.memory import StudioMemory
from agentic_odi_studio_api.studio.schemas import ChatMessage, ChatRequest

QUESTIONS = [
    "Who feels this problem most sharply today?",
    "What workaround do they use right now?",
    "What does that workaround cost them in time?",
]
STATEMENT = "Minimize the time it takes to file a claim"


def _request(**overrides: Any) -> ChatRequest:
    values: dict[str, Any] = {
        "base_url": "http://llm/v1",
        "api_key": "key",
        "model": "model",
        "mcp_url": "http://mcp",
        "messages": [ChatMessage(role="user", content="score this claim")],
    }
    values.update(overrides)
    return ChatRequest(**values)


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
    calls: list[tuple[str, dict[str, Any]]] = []
    tool_result: str = '{"id": "OUT-1", "statement": "x"}'

    def __init__(self, url: str) -> None:
        self.url = url

    async def __aenter__(self) -> _Mcp:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def list_tools(self) -> list[Any]:
        return [
            SimpleNamespace(
                name="add_outcome",
                description="Create an outcome",
                input_schema={"type": "object", "properties": {}},
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        _Mcp.calls.append((name, arguments))
        return _Mcp.tool_result


def _chunk(
    content: str | None = None,
    tool_calls: list[Any] | None = None,
) -> Any:
    delta = SimpleNamespace(content=content, tool_calls=tool_calls, reasoning_content=None)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _tool_call(arguments: str, name: str) -> Any:
    return SimpleNamespace(
        index=0,
        id="call-1",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _install(monkeypatch, streams: list[_FakeStream]) -> None:
    async def _healthy(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        return True, "ok"

    _Mcp.calls = []
    _Mcp.tool_result = '{"id": "OUT-1", "statement": "x"}'
    monkeypatch.setattr(chat, "check_llm_health", _healthy)
    monkeypatch.setattr(chat, "McpClient", _Mcp)
    monkeypatch.setattr(chat, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(chat, "AsyncOpenAI", lambda **kwargs: _FakeOpenAI(streams, **kwargs))


def _parse(frames: list[str]) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for frame in frames:
        name = None
        data = None
        for line in frame.splitlines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = line[len("data: ") :]
        if name and data is not None:
            events.append((name, json.loads(data)))
    return events


def _collect(request: ChatRequest, memory: StudioMemory) -> list[tuple[str, dict[str, Any]]]:
    async def _run() -> list[str]:
        return [frame async for frame in chat.stream_chat(request, memory=memory)]

    return _parse(asyncio.run(_run()))


def test_a_scored_write_with_no_plan_is_refused(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream(
                [
                    _chunk(
                        tool_calls=[
                            _tool_call(
                                json.dumps({"job_id": "JOB-1", "statement": STATEMENT, "importance": 8.6}),
                                "add_outcome",
                            )
                        ]
                    )
                ]
            ),
            _FakeStream([_chunk(content="I should ask you first.")]),
        ],
    )
    memory = StudioMemory(":memory:")
    try:
        events = _collect(_request(), memory)
    finally:
        memory.close()

    # Nothing reached the MCP tool, so no score was written.
    assert _Mcp.calls == []
    kinds = [name for name, _ in events]
    assert "score_gate" in kinds
    gate = next(data for name, data in events if name == "score_gate")
    assert "resolved score plan" in gate["reason"]


def test_prepare_score_streams_a_plan_that_is_not_recorded(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream(
                [
                    _chunk(
                        tool_calls=[
                            _tool_call(
                                json.dumps(
                                    {
                                        "statement": STATEMENT,
                                        "questions": QUESTIONS,
                                        "importance": 8.6,
                                        "satisfaction": 4.9,
                                    }
                                ),
                                "prepare_score",
                            )
                        ]
                    )
                ]
            ),
            _FakeStream([_chunk(content="Three questions for you.")]),
        ],
    )
    memory = StudioMemory(":memory:")
    try:
        events = _collect(_request(), memory)
    finally:
        memory.close()

    plan = next(data for name, data in events if name == "score_plan")
    assert plan["status"] == "open"
    assert plan["questions"] == QUESTIONS
    # prepare_score is a local tool: nothing was forwarded to MCP.
    assert _Mcp.calls == []


def test_a_model_supplied_claim_check_is_discarded(monkeypatch) -> None:
    memory = StudioMemory(":memory:")
    conversation = memory.create_conversation()
    plan = memory.open_score_plan(conversation.id, STATEMENT, QUESTIONS)
    memory.answer_score_plan(plan.id, ["Claims reps", "Email threads", "40 minutes"])

    _install(
        monkeypatch,
        [
            _FakeStream(
                [
                    _chunk(
                        tool_calls=[
                            _tool_call(
                                json.dumps(
                                    {
                                        "job_id": "JOB-1",
                                        "statement": STATEMENT,
                                        "importance": 8.6,
                                        "satisfaction": 4.9,
                                        # A check the model wrote for itself.
                                        "claim_check": {
                                            "asked": ["Did I check?"],
                                            "answers": ["yes"],
                                            "skips": [],
                                        },
                                    }
                                ),
                                "add_outcome",
                            )
                        ]
                    )
                ]
            ),
            _FakeStream([_chunk(content="Recorded with your answers.")]),
        ],
    )
    try:
        _collect(_request(conversation_id=conversation.id), memory)
    finally:
        memory.close()

    assert len(_Mcp.calls) == 1
    name, arguments = _Mcp.calls[0]
    assert name == "add_outcome"
    # Only the stored plan's basis is written; the model's own is gone.
    assert arguments["claim_check"]["asked"] == QUESTIONS
    assert arguments["claim_check"]["answers"] == ["Claims reps", "Email threads", "40 minutes"]
    assert "Did I check?" not in arguments["claim_check"]["asked"]


def test_a_skip_plan_lets_the_score_through_with_a_recorded_reason(monkeypatch) -> None:
    memory = StudioMemory(":memory:")
    conversation = memory.create_conversation()
    plan = memory.open_score_plan(conversation.id, STATEMENT, QUESTIONS)
    memory.skip_score_plan(plan.id, "No customer access this week")

    _install(
        monkeypatch,
        [
            _FakeStream(
                [
                    _chunk(
                        tool_calls=[
                            _tool_call(
                                json.dumps(
                                    {
                                        "job_id": "JOB-1",
                                        "statement": STATEMENT,
                                        "importance": 8.6,
                                        "satisfaction": 4.9,
                                    }
                                ),
                                "add_outcome",
                            )
                        ]
                    )
                ]
            ),
            _FakeStream([_chunk(content="Recorded as an assumption.")]),
        ],
    )
    try:
        _collect(_request(conversation_id=conversation.id), memory)
    finally:
        memory.close()

    assert len(_Mcp.calls) == 1
    _, arguments = _Mcp.calls[0]
    assert arguments["claim_check"]["answers"] == []
    assert arguments["claim_check"]["skips"]
    assert all(skip["reason"] == "No customer access this week" for skip in arguments["claim_check"]["skips"])


def test_an_unscored_outcome_is_never_gated(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream(
                [
                    _chunk(
                        tool_calls=[
                            _tool_call(
                                json.dumps({"job_id": "JOB-1", "statement": STATEMENT}),
                                "add_outcome",
                            )
                        ]
                    )
                ]
            ),
            _FakeStream([_chunk(content="Saved without a score.")]),
        ],
    )
    memory = StudioMemory(":memory:")
    try:
        events = _collect(_request(), memory)
    finally:
        memory.close()

    assert [name for name, _ in _Mcp.calls] == ["add_outcome"]
    assert not [data for name, data in events if name == "score_gate"]
