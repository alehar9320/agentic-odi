"""The turn's new parts: thinking, provenance, write approval, and attachments."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest
from agentic_odi_studio_api.studio import chat
from agentic_odi_studio_api.studio.approvals import (
    ApprovalDecision,
    ApprovalRegistry,
)
from agentic_odi_studio_api.studio.memory import StudioMemory
from agentic_odi_studio_api.studio.schemas import AttachmentRef, ChatMessage, ChatRequest


def _request(**overrides: Any) -> ChatRequest:
    values: dict[str, Any] = {
        "base_url": "http://llm/v1",
        "api_key": "key",
        "model": "model",
        "mcp_url": "http://mcp",
        "messages": [ChatMessage(role="user", content="list jobs", id="m-1")],
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
    tool_result: str = "ok"

    def __init__(self, url: str) -> None:
        self.url = url

    async def __aenter__(self) -> _Mcp:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def list_tools(self) -> list[Any]:
        return [
            SimpleNamespace(
                name="add_job",
                description="Create a job",
                input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            ),
            SimpleNamespace(
                name="get_jobs",
                description="List jobs",
                input_schema={"type": "object", "properties": {}},
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        _Mcp.calls.append((name, arguments))
        return _Mcp.tool_result


def _chunk(
    content: str | None = None,
    tool_calls: list[Any] | None = None,
    reasoning: str | None = None,
) -> Any:
    delta = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        reasoning_content=reasoning,
    )
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _tool_call(arguments: str, name: str = "get_jobs") -> Any:
    return SimpleNamespace(
        index=0,
        id="call-1",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _install(monkeypatch, streams: list[_FakeStream]) -> None:
    async def _healthy(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        return True, "ok"

    _Mcp.calls = []
    _Mcp.tool_result = "ok"
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


def _collect(request: ChatRequest, approvals: ApprovalRegistry | None = None) -> list[str]:
    async def _run() -> list[str]:
        return [frame async for frame in chat.stream_chat(request, approvals=approvals)]

    return asyncio.run(_run())


def _collect_answering(
    request: ChatRequest,
    approvals: ApprovalRegistry,
    decision: ApprovalDecision,
) -> list[str]:
    """Consume the turn, answering the first approval gate that appears."""

    async def _run() -> list[str]:
        frames: list[str] = []
        async for frame in chat.stream_chat(request, approvals=approvals):
            frames.append(frame)
            if frame.startswith("event: approval"):
                payload = json.loads(frame.split("data: ", 1)[1])
                approvals.resolve(payload["id"], decision)
        return frames

    return asyncio.run(_run())


def test_reasoning_is_streamed_separately_from_the_answer(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(reasoning="weighing options"), _chunk(content="Done.")]),
        ],
    )

    events = _parse(_collect(_request()))

    kinds = [name for name, _ in events]
    assert "reasoning" in kinds
    reasoning = next(data for name, data in events if name == "reasoning")
    assert reasoning["text"] == "weighing options"
    # Thinking is never part of the answer that replays as history.
    message = next(data for name, data in events if name == "message")
    assert message["content"] == "Done."


def test_a_tool_that_returned_data_becomes_a_source(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call("{}")])]),
            _FakeStream([_chunk(content="One job.")]),
        ],
    )
    _Mcp.tool_result = '[{"id": "JOB-1", "name": "Retention"}]'

    events = _parse(_collect(_request()))

    sources = [data for name, data in events if name == "source"]
    assert len(sources) == 1
    assert sources[0]["filename"] == "get_jobs"
    assert sources[0]["title"].startswith("get_jobs — ")
    assert "Retention" in sources[0]["title"]
    assert sources[0]["mediaType"] == "application/json"


def test_a_failed_tool_produces_no_source(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call("{}")])]),
            _FakeStream([_chunk(content="No such job.")]),
        ],
    )
    _Mcp.tool_result = "Error: Job with ID JOB-1 not found."

    events = _parse(_collect(_request()))

    assert not [data for name, data in events if name == "source"]


def test_the_approval_gate_does_not_appear_without_the_flag(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call('{"name":"Retention"}', "add_job")])]),
            _FakeStream([_chunk(content="Added.")]),
        ],
    )

    events = _parse(_collect(_request()))

    assert not [data for name, data in events if name == "approval"]
    assert _Mcp.calls == [("add_job", {"name": "Retention"})]


def test_an_approved_write_runs(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call('{"name":"Retention"}', "add_job")])]),
            _FakeStream([_chunk(content="Added.")]),
        ],
    )
    registry = ApprovalRegistry()

    frames = _collect_answering(_request(approvals=True), registry, ApprovalDecision(approved=True))
    events = _parse(frames)

    approval = next(data for name, data in events if name == "approval")
    assert approval["name"] == "add_job"
    assert approval["arguments"] == {"name": "Retention"}
    assert approval["prompt"] == "Allow the assistant to add job?"
    assert _Mcp.calls == [("add_job", {"name": "Retention"})]


def test_a_declined_write_never_runs_and_the_turn_still_ends(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call('{"name":"Retention"}', "add_job")])]),
            _FakeStream([_chunk(content="Understood, I left it alone.")]),
        ],
    )
    registry = ApprovalRegistry()

    frames = _collect_answering(
        _request(approvals=True),
        registry,
        ApprovalDecision(approved=False, reason="not yet"),
    )
    events = _parse(frames)

    assert _Mcp.calls == []
    declined = [data for name, data in events if name == "tool" and data["status"] == "declined"]
    assert len(declined) == 1
    assert "declined to run add_job" in declined[0]["preview"]
    assert "not yet" in declined[0]["preview"]
    terminals = [name for name, _ in events if name in {"message", "error"}]
    assert terminals == ["message"]


def test_an_expired_gate_tells_the_model_nothing_changed(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call('{"name":"Retention"}', "add_job")])]),
            _FakeStream([_chunk(content="I did not change anything.")]),
        ],
    )

    async def _expired(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(chat, "wait_for_decision", _expired)

    events = _parse(_collect(_request(approvals=True), approvals=ApprovalRegistry()))

    assert _Mcp.calls == []
    declined = [data for name, data in events if name == "tool" and data["status"] == "declined"]
    assert len(declined) == 1
    assert "expired" in declined[0]["preview"]
    assert [name for name, _ in events if name in {"message", "error"}] == ["message"]


@pytest.mark.parametrize(
    "name",
    [
        "schedule_work",
        "trigger_scheduled_work",
        "cancel_scheduled_work",
        "mark_signal_read",
        "dismiss_signal",
        "unknown_tool",
    ],
)
def test_declining_a_contract_write_or_unknown_tool_prevents_execution(monkeypatch, name) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call("{}", name)])]),
            _FakeStream([_chunk(content="Nothing changed.")]),
        ],
    )
    events = _parse(
        _collect_answering(
            _request(approvals=True), ApprovalRegistry(), ApprovalDecision(approved=False)
        )
    )
    assert [data["name"] for event, data in events if event == "approval"] == [name]
    assert _Mcp.calls == []


def test_approval_classification_preserves_reads_and_local_surfaces(monkeypatch) -> None:
    from agentic_odi_core.contract import TOOL_SPECS, ToolEffect, ToolSpec

    assert not chat.is_mutating_tool("get_jobs")
    assert not chat.is_mutating_tool("compute_opportunity")
    assert not chat.is_mutating_tool("evaluate_outcome")
    assert not chat.is_mutating_tool("remember")
    assert not chat.is_mutating_tool("render_ui")
    assert chat.is_mutating_tool("add_connector")
    monkeypatch.setitem(
        TOOL_SPECS,
        "get_future_write",
        ToolSpec(name="get_future_write", summary="writes", effect=ToolEffect.WRITE),
    )
    assert chat.is_mutating_tool("get_future_write")


def test_model_receives_visible_turn_history_in_order() -> None:
    request = _request(
        messages=[
            ChatMessage(role="user", content="Earlier question", id="m-1"),
            ChatMessage(role="assistant", content="Earlier answer", id="m-2"),
            ChatMessage(role="user", content="Latest question", id="m-3"),
        ]
    )

    messages = chat._to_openai_messages(request)

    assert messages[1:] == [
        {"role": "user", "content": "Earlier question"},
        {"role": "assistant", "content": "Earlier answer"},
        {"role": "user", "content": "Latest question"},
    ]


def test_attachment_text_is_part_of_the_user_turn_the_model_reads() -> None:
    request = _request(
        attachments=[
            AttachmentRef(
                name="call-notes.md",
                content_type="text/markdown",
                size=120,
                text="Customer said the export is too slow.",
            )
        ]
    )

    messages = chat._to_openai_messages(request)
    user = messages[-1]

    assert user["role"] == "user"
    assert "Customer said the export is too slow." in user["content"]
    assert "[Attached file: call-notes.md]" in user["content"]


def test_an_image_attachment_becomes_a_vision_part() -> None:
    request = _request(
        attachments=[
            AttachmentRef(
                name="whiteboard.png",
                content_type="image/png",
                size=2048,
                data_url="data:image/png;base64,AAAA",
            )
        ]
    )

    user = chat._to_openai_messages(request)[-1]

    assert isinstance(user["content"], list)
    assert user["content"][0]["type"] == "text"
    assert user["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,AAAA"},
    }


def test_attachments_are_bounded(monkeypatch) -> None:
    attachments = [
        AttachmentRef(name=f"note-{index}.md", content_type="text/markdown", text="x" * 500)
        for index in range(9)
    ]

    block = chat._attachment_block(attachments)

    assert block.count("[Attached file:") == chat.MAX_ATTACHMENTS


def test_attachment_text_is_truncated(monkeypatch) -> None:
    block = chat._attachment_block(
        [AttachmentRef(name="big.md", content_type="text/markdown", text="y" * 50_000)]
    )

    assert len(block) < 50_000
    assert chat.MAX_ATTACHMENT_TEXT < 50_000


def test_a_cited_sentence_names_the_record_not_the_tool(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call("{}", "list_evidence")])]),
            _FakeStream([_chunk(content="Three accounts stalled. [[ev:E-1]]")]),
        ],
    )
    _Mcp.tool_result = '[{"id": "E-1", "name": "Call with Acme", "source_name": "Gong"}]'

    events = _parse(_collect(_request()))

    message = next(data for name, data in events if name == "message")
    assert message["content"] == "Three accounts stalled. [[ev:E-1]]"
    assert message["claims"] == [
        {
            "index": 0,
            "text": "Three accounts stalled.",
            "status": "cited",
            "evidence": [{"id": "E-1", "name": "Call with Acme", "source_name": "Gong"}],
            "reason": None,
        }
    ]


def test_an_id_the_turn_never_received_is_downgraded(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call("{}", "list_evidence")])]),
            _FakeStream([_chunk(content="They churned. [[ev:E-9]]")]),
        ],
    )
    _Mcp.tool_result = "[]"

    events = _parse(_collect(_request()))

    claim = next(data for name, data in events if name == "message")["claims"][0]
    assert claim["status"] == "uncited"
    assert claim["reason"] == "unknown_evidence_id"
    assert claim["evidence"] == []


def test_a_hypothesis_and_an_unmarked_sentence_still_reach_the_reader(monkeypatch) -> None:
    _install(
        monkeypatch,
        [_FakeStream([_chunk(content="Nobody said why. [[hypothesis]] It is a guess.")])],
    )

    events = _parse(_collect(_request()))

    claims = next(data for name, data in events if name == "message")["claims"]
    assert [claim["status"] for claim in claims] == ["hypothesis", "uncited"]
    assert [name for name, _ in events if name in {"message", "error"}] == ["message"]


def test_an_offline_reply_carries_no_claims(monkeypatch) -> None:
    async def _unhealthy(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        return False, "down"

    monkeypatch.setattr(chat, "check_llm_health", _unhealthy)
    monkeypatch.setattr(chat, "is_endpoint_reachable", lambda url, timeout: True)

    events = _parse(_collect(_request()))

    message = next(data for name, data in events if name == "message")
    assert "claims" not in message


def test_claims_are_persisted_with_the_turn(monkeypatch) -> None:
    _install(
        monkeypatch,
        [
            _FakeStream([_chunk(tool_calls=[_tool_call("{}", "list_evidence")])]),
            _FakeStream([_chunk(content="Three accounts stalled. [[ev:E-1]]")]),
        ],
    )
    _Mcp.tool_result = '[{"id": "E-1", "name": "Call with Acme", "source_name": "Gong"}]'
    memory = StudioMemory(":memory:")

    async def _run() -> list[str]:
        return [frame async for frame in chat.stream_chat(_request(), memory=memory)]

    asyncio.run(_run())

    conversation = memory.latest_conversation()
    assert conversation is not None
    assistant = memory.conversation_tree(conversation.id)[-1]
    assert assistant.claims[0].status == "cited"
    assert assistant.claims[0].evidence[0].name == "Call with Acme"
