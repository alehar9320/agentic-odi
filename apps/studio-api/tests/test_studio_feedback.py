"""Message feedback stays local: one row per reply, replaceable, summarised honestly."""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio.memory import StudioMemory
from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(create_app(repo=InMemoryRepository(), memory=StudioMemory(":memory:")))


def _conversation(client: TestClient) -> str:
    return client.post("/api/conversations").json()["conversation"]["id"]


def test_a_later_verdict_replaces_the_earlier_one() -> None:
    client = _client()
    conversation_id = _conversation(client)

    first = client.post(
        "/api/feedback",
        json={"conversation_id": conversation_id, "message_id": "m-2", "type": "positive"},
    )
    assert first.status_code == 200
    assert first.json()["feedback"]["type"] == "positive"

    second = client.post(
        "/api/feedback",
        json={"conversation_id": conversation_id, "message_id": "m-2", "type": "negative"},
    )
    assert second.status_code == 200

    summary = client.get("/api/feedback/summary").json()
    assert summary == {"positive": 0, "negative": 1}


def test_an_invalid_verdict_is_refused() -> None:
    client = _client()
    conversation_id = _conversation(client)
    response = client.post(
        "/api/feedback",
        json={"conversation_id": conversation_id, "message_id": "m-2", "type": "maybe"},
    )
    assert response.status_code == 422


def test_feedback_for_an_unknown_conversation_is_not_found() -> None:
    client = _client()
    response = client.post(
        "/api/feedback",
        json={"conversation_id": "nope", "message_id": "m-2", "type": "positive"},
    )
    assert response.status_code == 404


def test_an_empty_summary_reads_zero_not_a_guess() -> None:
    client = _client()
    assert client.get("/api/feedback/summary").json() == {"positive": 0, "negative": 0}


def test_clearing_memory_clears_feedback() -> None:
    memory = StudioMemory(":memory:")
    client = TestClient(create_app(repo=InMemoryRepository(), memory=memory))
    conversation_id = _conversation(client)
    client.post(
        "/api/feedback",
        json={"conversation_id": conversation_id, "message_id": "m-2", "type": "positive"},
    )
    assert client.get("/api/feedback/summary").json()["positive"] == 1

    memory.clear_memory()
    assert client.get("/api/feedback/summary").json() == {"positive": 0, "negative": 0}


def test_a_comment_is_stored_and_capped() -> None:
    memory = StudioMemory(":memory:")
    client = TestClient(create_app(repo=InMemoryRepository(), memory=memory))
    conversation_id = _conversation(client)
    client.post(
        "/api/feedback",
        json={
            "conversation_id": conversation_id,
            "message_id": "m-2",
            "type": "negative",
            "comment": "the arithmetic was wrong",
        },
    )
    stored = memory.record_feedback(
        conversation_id=conversation_id,
        message_id="m-3",
        type="negative",
        comment="x" * 900,
    )
    assert stored.comment is not None and len(stored.comment) == 500


def test_a_conversation_lists_its_own_verdicts_newest_first() -> None:
    client = _client()
    conversation_id = _conversation(client)
    for message_id in ("m-1", "m-2"):
        client.post(
            "/api/feedback",
            json={"conversation_id": conversation_id, "message_id": message_id, "type": "positive"},
        )
    response = client.get(f"/api/conversations/{conversation_id}/feedback")
    assert response.status_code == 200
    ids = [row["message_id"] for row in response.json()["feedback"]]
    assert sorted(ids) == ["m-1", "m-2"]


def test_listing_feedback_for_an_unknown_conversation_is_not_found() -> None:
    client = _client()
    assert client.get("/api/conversations/nope/feedback").status_code == 404
