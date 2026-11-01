"""Conversations keep a branch tree, and old rows still open."""

from __future__ import annotations

import sqlite3

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio.claims import (
    EvidenceIndex,
    EvidenceSnapshot,
    split_claims,
)
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


def test_the_conversation_list_is_ordered_by_the_last_touch(tmp_path) -> None:
    path = tmp_path / "studio.db"
    memory = StudioMemory(path)
    # Created in one order, touched in the other: the list follows recency.
    revisited = memory.create_conversation("Quarterly review")
    untouched = memory.create_conversation("Activation model")
    memory.close()

    connection = sqlite3.connect(path)
    with connection:
        connection.execute(
            "UPDATE conversations SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2026-01-01T00:00:00+00:00", "2026-02-09T00:00:00+00:00", revisited.id),
        )
        connection.execute(
            "UPDATE conversations SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2026-02-05T00:00:00+00:00", "2026-02-05T00:00:00+00:00", untouched.id),
        )
    connection.close()

    listed = StudioMemory(path).list_conversations()

    assert [item.id for item in listed] == [revisited.id, untouched.id]


def test_the_conversation_list_counts_the_turns_of_each_conversation() -> None:
    memory = _memory()
    talked = memory.create_conversation()
    quiet = memory.create_conversation()
    memory.append_turn(talked.id, "user", "How do I score this?", "m-1", None)
    memory.append_turn(talked.id, "assistant", "By importance and satisfaction.", "m-2", "m-1")

    counts = {item.id: item.turn_count for item in memory.list_conversations()}

    assert counts == {talked.id: 2, quiet.id: 0}


def test_the_conversation_list_keeps_the_fields_a_switcher_needs() -> None:
    memory = _memory()
    blank = memory.create_conversation()
    branch = memory.create_conversation("Activation model")
    memory.append_turn(branch.id, "user", "list jobs", "m-1", None)
    memory.append_turn(branch.id, "assistant", "first", "m-2", "m-1")
    memory.append_turn(branch.id, "assistant", "second", "m-3", "m-1")
    memory.set_head(branch.id, "m-3")

    listed = {item.id: item for item in memory.list_conversations()}

    assert listed[blank.id].to_dict() == {
        "id": blank.id,
        "title": "",
        "created_at": blank.created_at,
        "updated_at": blank.updated_at,
        "head_id": None,
        "turn_count": 0,
    }
    assert listed[branch.id].head_id == "m-3"


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


def _evidence_index() -> EvidenceIndex:
    index = EvidenceIndex()
    index.remember(EvidenceSnapshot("E-1", "Call with Acme", "Gong"))
    return index


CONTENT = "Three accounts stalled. [[ev:E-1]] Nobody said why. [[hypothesis]]"


def test_claims_are_stored_beside_the_turn_and_restored_by_index() -> None:
    memory = _memory()
    conversation = memory.create_conversation()

    turn_id = memory.append_turn(conversation.id, "assistant", CONTENT, "m-1", None)
    memory.add_citations(turn_id, split_claims(CONTENT, _evidence_index()))

    restored = memory.conversation_tree(conversation.id)[0].claims

    assert [claim.status for claim in restored] == ["cited", "hypothesis"]
    assert restored[0].text == "Three accounts stalled."
    assert [snapshot.to_dict() for snapshot in restored[0].evidence] == [
        {"id": "E-1", "name": "Call with Acme", "source_name": "Gong"}
    ]


def test_a_duplicate_retry_does_not_duplicate_rows() -> None:
    memory = _memory()
    conversation = memory.create_conversation()
    claims = split_claims(CONTENT, _evidence_index())

    turn_id = memory.append_turn(conversation.id, "assistant", CONTENT, "m-1", None)
    memory.add_citations(turn_id, claims)
    memory.add_citations(turn_id, claims)

    assert len(memory.citations_for_turn(turn_id)) == len(claims)


def test_a_count_mismatch_drops_the_citations_instead_of_mis_attaching_them() -> None:
    memory = _memory()
    conversation = memory.create_conversation()

    turn_id = memory.append_turn(conversation.id, "assistant", "Only one sentence.", "m-1", None)
    memory.add_citations(turn_id, split_claims("First. Second.", _evidence_index()))

    assert memory.conversation_tree(conversation.id)[0].claims == []


def test_the_tree_endpoint_restores_claims_with_their_labels() -> None:
    memory = _memory()
    conversation = memory.create_conversation()
    turn_id = memory.append_turn(conversation.id, "assistant", CONTENT, "m-1", None)
    memory.add_citations(turn_id, split_claims(CONTENT, _evidence_index()))
    client = TestClient(create_app(repo=InMemoryRepository(), memory=memory))

    body = client.get(f"/api/conversations/{conversation.id}/tree").json()

    claims = body["messages"][0]["claims"]
    assert [claim["status"] for claim in claims] == ["cited", "hypothesis"]
    assert claims[0]["evidence"] == [{"id": "E-1", "name": "Call with Acme", "source_name": "Gong"}]
