"""Conversations keep a branch tree, and old rows still open."""

from __future__ import annotations

import sqlite3

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio.memory import StudioMemory
from fastapi.testclient import TestClient


def _memory() -> StudioMemory:
    return StudioMemory(":memory:")


def test_turns_keep_the_client_message_ids() -> None:
    memory = _memory()
    conversation = memory.create_conversation()

    memory.append_turn(conversation.id, "user", "list jobs", "m-1", None)
    memory.append_turn(conversation.id, "assistant", "here they are", "m-2", "m-1")

    turns = memory.list_turns(conversation.id)
    assert [(turn.message_id, turn.parent_id) for turn in turns] == [
        ("m-1", None),
        ("m-2", "m-1"),
    ]
    assert memory.get_conversation(conversation.id).head_id == "m-2"  # type: ignore[union-attr]


def test_a_second_answer_to_the_same_question_is_a_sibling() -> None:
    memory = _memory()
    conversation = memory.create_conversation()

    memory.append_turn(conversation.id, "user", "list jobs", "m-1", None)
    memory.append_turn(conversation.id, "assistant", "first", "m-2", "m-1")
    memory.append_turn(conversation.id, "assistant", "second", "m-3", "m-1")

    parents = {
        turn.message_id: turn.parent_id for turn in memory.conversation_tree(conversation.id)
    }
    assert parents == {"m-1": None, "m-2": "m-1", "m-3": "m-1"}

    memory.set_head(conversation.id, "m-2")
    assert memory.get_conversation(conversation.id).head_id == "m-2"  # type: ignore[union-attr]


def test_legacy_rows_are_read_as_a_linear_chain(tmp_path) -> None:
    path = tmp_path / "studio.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL, role TEXT NOT NULL,
            content TEXT NOT NULL, created_at TEXT NOT NULL
        );
        INSERT INTO conversations VALUES ('c1', 'Old', 'now', 'now');
        INSERT INTO turns (conversation_id, role, content, created_at)
            VALUES ('c1', 'user', 'hello', 'now');
        INSERT INTO turns (conversation_id, role, content, created_at)
            VALUES ('c1', 'assistant', 'hi', 'now');
        """
    )
    connection.commit()
    connection.close()

    memory = StudioMemory(path)
    turns = memory.conversation_tree("c1")

    assert [(turn.message_id, turn.parent_id) for turn in turns] == [
        ("turn-1", None),
        ("turn-2", "turn-1"),
    ]
    assert memory.get_conversation("c1").head_id is None  # type: ignore[union-attr]


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


def test_the_tree_endpoint_reports_an_unknown_conversation() -> None:
    app = create_app(repo=InMemoryRepository(), memory=_memory())
    client = TestClient(app)

    response = client.get("/api/conversations/missing/tree")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_patching_the_head_moves_the_visible_branch() -> None:
    memory = _memory()
    conversation = memory.create_conversation()
    memory.append_turn(conversation.id, "user", "list jobs", "m-1", None)
    memory.append_turn(conversation.id, "assistant", "first", "m-2", "m-1")
    memory.append_turn(conversation.id, "assistant", "second", "m-3", "m-1")
    app = create_app(repo=InMemoryRepository(), memory=memory)
    client = TestClient(app)

    response = client.patch(f"/api/conversations/{conversation.id}", json={"head_id": "m-2"})

    assert response.status_code == 200
    assert response.json()["conversation"]["head_id"] == "m-2"
    assert memory.get_conversation(conversation.id).head_id == "m-2"  # type: ignore[union-attr]


def test_patching_an_unknown_conversation_is_a_404() -> None:
    app = create_app(repo=InMemoryRepository(), memory=_memory())
    client = TestClient(app)

    response = client.patch("/api/conversations/missing", json={"head_id": "m-1"})

    assert response.status_code == 404


def test_an_approval_can_be_answered_through_the_api() -> None:
    app = create_app(repo=InMemoryRepository(), memory=_memory())
    client = TestClient(app)

    response = client.post("/api/approvals/apv_missing", json={"approved": True})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
