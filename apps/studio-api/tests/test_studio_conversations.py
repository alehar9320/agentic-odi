"""Durable conversations: the routes, both backends, and the memory event.

The thread is stored in the core event log, so the routes answer the same way
whether the sidecar is running its own tools or fronting an MCP server, and the
``remember`` tool reaches the client as a ``memory`` event it can confirm. The
branch tree and a rename that keeps the selected branch are covered here, and
the pre-core rows are covered in ``test_studio_memory.py``: together they are
the behaviour the Studio relies on when a person reloads the page.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import chat
from agentic_odi_studio_api.studio.memory import ConversationNotFoundError, StudioMemory
from fastapi.testclient import TestClient

BACKENDS = ("local", "mcp")


def _memory() -> StudioMemory:
    return StudioMemory(":memory:")


def _pair(backend: str) -> tuple[TestClient, StudioMemory]:
    """One store behind the canvas, the thread, and the routes."""
    repo = InMemoryRepository()
    memory = StudioMemory(repo)
    return TestClient(create_app(repo=repo, memory=memory, backend=backend)), memory


def _thread(memory: StudioMemory) -> str:
    conversation = memory.create_conversation()
    memory.append_turn(conversation.id, "user", "list jobs", "m-1")
    memory.append_turn(conversation.id, "assistant", "here they are", "m-2", "m-1")
    return conversation.id


# -- the branch tree the sidecar keeps --------------------------------------


def test_turns_keep_the_client_message_ids() -> None:
    memory = _memory()
    conversation = memory.create_conversation()

    memory.append_turn(conversation.id, "user", "list jobs", "m-1", None)
    memory.append_turn(conversation.id, "assistant", "here they are", "m-2", "m-1")

    turns = memory.list_turns(conversation.id)
    assert [(turn.id, turn.parent_id) for turn in turns] == [("m-1", None), ("m-2", "m-1")]
    assert memory.get_conversation(conversation.id).head_id == "m-2"  # type: ignore[union-attr]


def test_a_second_answer_to_the_same_question_is_a_sibling() -> None:
    memory = _memory()
    conversation = memory.create_conversation()

    memory.append_turn(conversation.id, "user", "list jobs", "m-1", None)
    memory.append_turn(conversation.id, "assistant", "first", "m-2", "m-1")
    memory.append_turn(conversation.id, "assistant", "second", "m-3", "m-1")

    parents = {turn.id: turn.parent_id for turn in memory.conversation_tree(conversation.id)}
    assert parents == {"m-1": None, "m-2": "m-1", "m-3": "m-1"}

    memory.set_head(conversation.id, "m-2")
    assert memory.get_conversation(conversation.id).head_id == "m-2"  # type: ignore[union-attr]


def test_rename_keeps_the_tree() -> None:
    memory = _memory()
    conversation = memory.create_conversation()

    renamed = memory.update_title(conversation.id, "Retention work")

    assert renamed.title == "Retention work"
    assert renamed.head_id is None


def test_the_tree_endpoint_returns_messages_and_the_head() -> None:
    memory = _memory()
    conversation = memory.create_conversation()
    memory.append_turn(conversation.id, "user", "list jobs", "m-1", None)
    memory.append_turn(conversation.id, "assistant", "here they are", "m-2", "m-1")
    app = create_app(repo=InMemoryRepository(), memory=memory)
    client = TestClient(app)

    body = client.get(f"/api/conversations/{conversation.id}/tree").json()

    assert body["conversation"]["id"] == conversation.id
    assert body["head_id"] == "m-2"
    assert [message["id"] for message in body["messages"]] == ["m-1", "m-2"]
    assert body["messages"][1]["parent_id"] == "m-1"
    assert body["messages"][1]["content"] == "here they are"


def test_renaming_a_conversation_keeps_the_selected_branch() -> None:
    memory = _memory()
    conversation = memory.create_conversation()
    memory.append_turn(conversation.id, "user", "list jobs", "m-1", None)
    memory.append_turn(conversation.id, "assistant", "first", "m-2", "m-1")
    memory.append_turn(conversation.id, "assistant", "second", "m-3", "m-1")
    memory.set_head(conversation.id, "m-2")
    app = create_app(repo=InMemoryRepository(), memory=memory)
    client = TestClient(app)

    response = client.patch(f"/api/conversations/{conversation.id}", json={"title": "Renamed"})

    assert response.status_code == 200
    assert response.json()["conversation"]["head_id"] == "m-2"
    assert memory.get_conversation(conversation.id).head_id == "m-2"  # type: ignore[union-attr]


def test_an_approval_can_be_answered_through_the_api() -> None:
    app = create_app(repo=InMemoryRepository(), memory=_memory())
    client = TestClient(app)

    response = client.post("/api/approvals/apv_missing", json={"approved": True})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# -- the routes, under both backends ---------------------------------------


@pytest.mark.parametrize("backend", BACKENDS)
def test_creating_listing_renaming_and_deleting_a_conversation(backend: str) -> None:
    client, memory = _pair(backend)

    created = client.post("/api/conversations").json()["conversation"]
    assert created["title"] is None
    assert created["archived"] is False

    listed = client.get("/api/conversations").json()["conversations"]
    assert [item["id"] for item in listed] == [created["id"]]

    renamed = client.patch(
        f"/api/conversations/{created['id']}", json={"title": "Secrets rotation"}
    ).json()["conversation"]
    assert renamed["title"] == "Secrets rotation"

    assert client.delete(f"/api/conversations/{created['id']}").status_code == 200
    assert client.get("/api/conversations").json()["conversations"] == []
    assert memory.get_conversation(created["id"]) is None


@pytest.mark.parametrize("backend", BACKENDS)
def test_messages_append_and_read_back_in_order_with_their_parts(backend: str) -> None:
    client, _memory = _pair(backend)
    created = client.post("/api/conversations").json()["conversation"]
    conversation_id = created["id"]

    user = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"role": "user", "content": "what is underserved?", "id": "u-1"},
    ).json()["message"]
    assistant = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={
            "role": "assistant",
            "content": "the board below",
            "id": "a-1",
            "parent_id": "u-1",
            "parts": [{"kind": "ui", "id": "ui-1", "node": {"type": "outcome-board"}}],
        },
    ).json()["message"]

    assert user["parent_id"] is None
    assert assistant["parent_id"] == "u-1"
    messages = client.get(f"/api/conversations/{conversation_id}/messages").json()["messages"]
    assert [item["id"] for item in messages] == ["u-1", "a-1"]
    assert messages[1]["parts"][0]["node"]["type"] == "outcome-board"

    one_page = client.get(
        f"/api/conversations/{conversation_id}/messages", params={"limit": 1}
    ).json()["messages"]
    assert [item["id"] for item in one_page] == ["u-1"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_getting_one_conversation_returns_its_transcript(backend: str) -> None:
    client, memory = _pair(backend)
    conversation_id = _thread(memory)

    body = client.get(f"/api/conversations/{conversation_id}").json()

    assert body["conversation"]["id"] == conversation_id
    assert body["conversation"]["head_id"] == "m-2"
    assert [message["role"] for message in body["messages"]] == ["user", "assistant"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_unknown_ids_are_a_typed_not_found(backend: str) -> None:
    client, _memory = _pair(backend)

    for path in (
        "/api/conversations/missing",
        "/api/conversations/missing/tree",
        "/api/conversations/missing/messages",
    ):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    assert client.patch("/api/conversations/missing", json={"title": "x"}).status_code == 404
    assert client.delete("/api/conversations/missing").status_code == 404
    append = client.post(
        "/api/conversations/missing/messages", json={"role": "user", "content": "hi"}
    )
    assert append.status_code == 404


@pytest.mark.parametrize("backend", BACKENDS)
def test_appending_and_reading_observations(backend: str) -> None:
    client, _memory = _pair(backend)

    created = client.post(
        "/api/observations", json={"category": "constraint", "text": "Legal review is slow."}
    ).json()["observation"]
    assert created["status"] == "proposed"

    proposed = client.get("/api/observations", params={"status": "proposed"}).json()["observations"]
    assert [item["id"] for item in proposed] == [created["id"]]
    assert (
        client.get("/api/observations", params={"status": "confirmed"}).json()["observations"] == []
    )

    confirmed = client.patch(
        f"/api/observations/{created['id']}", json={"status": "confirmed"}
    ).json()["observation"]
    assert confirmed["status"] == "confirmed"

    forgotten = client.delete(f"/api/observations/{created['id']}")
    assert forgotten.status_code == 200
    assert client.get("/api/observations").json()["observations"] == []


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_dismissed_observation_leaves_the_default_list(backend: str) -> None:
    client, _memory = _pair(backend)
    kept = client.post("/api/observations", json={"text": "Growth is the mandate."}).json()[
        "observation"
    ]
    dropped = client.post("/api/observations", json={"text": "A wrong guess."}).json()[
        "observation"
    ]

    client.patch(f"/api/observations/{dropped['id']}", json={"status": "dismissed"})

    listed = client.get("/api/observations").json()["observations"]
    assert [item["id"] for item in listed] == [kept["id"]]


# -- the thread the chat loop writes ---------------------------------------


@pytest.mark.parametrize("backend", BACKENDS)
def test_a_chat_turn_is_stored_and_read_back(backend: str) -> None:
    client, _memory = _pair(backend)

    with client.stream("POST", "/api/chat", json=_chat_body("hello there")) as response:
        assert response.status_code == 200
        events = _sse_events("".join(response.iter_text()))

    conversation_id = json.loads(events["conversation"][0])["id"]
    transcript = client.get(f"/api/conversations/{conversation_id}").json()["messages"]
    assert [turn["role"] for turn in transcript] == ["user", "assistant"]
    assert transcript[0]["content"] == "hello there"
    assert transcript[1]["parts"][0]["kind"] == "text"


def _chat_body(content: str) -> dict[str, Any]:
    return {
        "base_url": "http://127.0.0.1:1/v1",
        "api_key": "k",
        "model": "m",
        "mcp_url": "http://127.0.0.1:1/mcp",
        "messages": [{"role": "user", "content": content, "id": "u-1"}],
    }


def _sse_events(body: str) -> dict[str, list[str]]:
    events: dict[str, list[str]] = {}
    for block in body.split("\n\n"):
        name = None
        data: list[str] = []
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data.append(line[len("data: ") :])
        if name:
            events.setdefault(name, []).append("".join(data))
    return events


# -- the memory event over HTTP --------------------------------------------


class _FakeStream:
    def __init__(self, chunks: list[Any]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> Any:
        async def _gen() -> Any:
            for chunk in self._chunks:
                yield chunk

        return _gen()


class _FakeOpenAI:
    def __init__(self, streams: list[_FakeStream], **kwargs: Any) -> None:
        async def create(**_kwargs: Any) -> _FakeStream:
            return streams.pop(0)

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


class _FakeMcp:
    def __init__(self, url: str) -> None:
        self.url = url

    async def __aenter__(self) -> _FakeMcp:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def list_tools(self) -> list[Any]:
        return []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        raise AssertionError(f"{name} is a local tool and must not reach MCP")


def _delta_chunk(content: str | None = None, tool_calls: list[Any] | None = None) -> Any:
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _tool_call(name: str, arguments: dict[str, Any]) -> Any:
    return SimpleNamespace(
        index=0,
        id="call-1",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


@pytest.fixture()
def _remote_model(monkeypatch) -> None:
    """A reachable LLM and MCP server, with the answers the test supplies."""

    async def _healthy(*args: Any, **kwargs: Any) -> tuple[bool, str]:
        return True, "ok"

    monkeypatch.setattr(chat, "check_llm_health", _healthy)
    monkeypatch.setattr(chat, "McpClient", _FakeMcp)
    monkeypatch.setattr(chat, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(
        chat,
        "AsyncOpenAI",
        lambda **kwargs: _FakeOpenAI(
            [
                _FakeStream(
                    [
                        _delta_chunk(
                            tool_calls=[
                                _tool_call(
                                    "remember",
                                    {"category": "career", "text": "Owns activation."},
                                )
                            ]
                        )
                    ]
                ),
                _FakeStream([_delta_chunk("Noted.")]),
            ],
            **kwargs,
        ),
    )


def _reachable_chat_body(content: str) -> dict[str, Any]:
    return {
        "base_url": "http://llm.test/v1",
        "api_key": "k",
        "model": "m",
        "mcp_url": "http://mcp.test/mcp",
        "messages": [{"role": "user", "content": content, "id": "u-1"}],
    }


@pytest.mark.parametrize("backend", BACKENDS)
def test_remember_emits_a_memory_event_and_proposes_for_confirmation(
    backend: str, _remote_model: None
) -> None:
    client, memory = _pair(backend)

    with client.stream("POST", "/api/chat", json=_reachable_chat_body("I own activation.")) as r:
        assert r.status_code == 200
        events = _sse_events("".join(r.iter_text()))

    payload = json.loads(events["memory"][0])["observation"]
    assert payload["status"] == "proposed"
    assert payload["category"] == "career"
    assert payload["text"] == "Owns activation."
    stored = memory.list_observations()
    assert [item.text for item in stored] == ["Owns activation."]
    assert stored[0].source_message_id == "u-1"
    assert stored[0].conversation_id == json.loads(events["conversation"][0])["id"]


def test_the_prompt_block_carries_only_what_the_person_confirmed() -> None:
    """A proposal never reaches the model; a confirmation always does."""
    _client, memory = _pair("local")
    conversation_id = _thread(memory)

    proposed = memory.add_observation("career", "Owns activation.", conversation_id=conversation_id)
    assert memory.memory_context() == ""

    memory.update_observation(proposed.id, status="confirmed")
    assert "Owns activation." in memory.memory_context()

    memory.update_observation(proposed.id, status="dismissed")
    assert memory.memory_context() == ""


def test_the_sidecar_never_calls_the_llm_to_read_or_write_the_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The thread lives in the store; no model is consulted to restore it."""

    def _forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the conversation routes must not build an LLM client")

    monkeypatch.setattr(chat, "AsyncOpenAI", _forbidden)
    client, memory = _pair("local")
    conversation_id = _thread(memory)

    assert client.get(f"/api/conversations/{conversation_id}").status_code == 200
    assert (
        client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"role": "user", "content": "and the blockers?", "id": "m-9", "parent_id": "m-2"},
        ).status_code
        == 200
    )
    assert (
        client.patch(f"/api/conversations/{conversation_id}", json={"head_id": "m-9"}).status_code
        == 200
    )
    assert [turn.id for turn in memory.list_turns(conversation_id)] == ["m-1", "m-2", "m-9"]


def test_clearing_memory_forgets_the_thread_and_the_facts() -> None:
    client, memory = _pair("local")
    _thread(memory)
    memory.add_observation("career", "Owns activation.")

    assert client.delete("/api/memory").status_code == 200

    assert memory.list_conversations() == []
    assert memory.list_observations() == []
    with pytest.raises(ConversationNotFoundError):
        memory.list_turns("anything")


def test_the_store_is_shared_with_the_tools_the_cli_uses() -> None:
    """One log: what the sidecar appends, the MCP/CLI service reads back."""
    from agentic_odi_core import ODIService

    _client, memory = _pair("local")
    conversation_id = _thread(memory)
    memory.add_observation("career", "Owns activation.", status="confirmed")

    service = ODIService(memory.service.repo)
    thread = service.conversation_thread(conversation_id)
    assert [message.content for message in thread] == ["list jobs", "here they are"]
    assert [item.text for item in service.confirmed_observations()] == ["Owns activation."]
    listed = service.list_conversations(limit=20)
    assert [conversation.id for conversation in listed] == [conversation_id]


def test_a_turn_is_not_written_twice_when_the_client_retries() -> None:
    client, memory = _pair("local")
    conversation_id = _thread(memory)
    payload = {"role": "user", "content": "and the blockers?", "id": "m-1", "parent_id": None}

    again = client.post(f"/api/conversations/{conversation_id}/messages", json=payload).json()[
        "message"
    ]

    assert again["content"] == "list jobs"
    assert [turn.id for turn in memory.list_turns(conversation_id)] == ["m-1", "m-2"]


def test_the_latest_conversation_reopens_with_its_parts() -> None:
    client, memory = _pair("local")
    conversation = memory.create_conversation()
    memory.append_turn(
        conversation.id,
        "assistant",
        "board below",
        "a-1",
        parts=[{"kind": "ui", "id": "ui-1", "node": {"type": "outcome-board"}}],
    )

    body = client.get("/api/conversations/latest").json()

    assert body["conversation"]["id"] == conversation.id
    assert body["turns"][0]["parts"][0]["node"]["type"] == "outcome-board"


def test_archiving_a_thread_keeps_it_readable() -> None:
    client, memory = _pair("local")
    conversation_id = _thread(memory)

    archived = client.patch(
        f"/api/conversations/{conversation_id}", json={"archived": True}
    ).json()["conversation"]

    assert archived["archived"] is True
    assert archived["head_id"] == "m-2"
    assert len(client.get(f"/api/conversations/{conversation_id}/messages").json()["messages"]) == 2


def test_patching_the_head_reopens_the_branch_that_was_on_screen() -> None:
    client, memory = _pair("local")
    conversation_id = _thread(memory)
    memory.append_turn(conversation_id, "assistant", "second", "m-3", "m-1")

    patched = client.patch(f"/api/conversations/{conversation_id}", json={"head_id": "m-2"})

    assert patched.json()["conversation"]["head_id"] == "m-2"
    tree = client.get(f"/api/conversations/{conversation_id}/tree").json()
    assert tree["head_id"] == "m-2"
    assert {message["id"]: message["parent_id"] for message in tree["messages"]} == {
        "m-1": None,
        "m-2": "m-1",
        "m-3": "m-1",
    }


def test_the_conversation_id_survives_a_second_request() -> None:
    """The SPA keeps one thread across turns, so the log has one conversation."""
    client, _memory = _pair("local")

    with client.stream("POST", "/api/chat", json=_chat_body("first")) as first:
        first_id = json.loads(_sse_events("".join(first.iter_text()))["conversation"][0])["id"]
    second_body = {**_chat_body("second"), "conversation_id": first_id}
    with client.stream("POST", "/api/chat", json=second_body) as second:
        second_id = json.loads(_sse_events("".join(second.iter_text()))["conversation"][0])["id"]

    assert second_id == first_id
    assert len(client.get("/api/conversations").json()["conversations"]) == 1
