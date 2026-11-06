"""The next step through the sidecar: one open promise, readable on the return (ALH-146, M0-14).

Four routes over the core service, in the shapes this router already uses for
entities: a read that answers ``null`` when nothing is outstanding, a POST that
records what the person means to do, a PATCH for the two answers that move the
row and record nothing (reschedule, drop), and a verb route for the answer that
produces a record — resolve, which writes evidence the way
``/evidence/{id}/promote`` writes a promotion.

Both backends must serve the same thing, so a ``null`` from the store stays a
``null`` and never becomes an empty list a greeting would read as a step with
blank text. A body value the domain refuses answers 400 with code
``validation`` — the status this sidecar already uses for a bad field, not the
422 FastAPI reserves for a body that fails to parse.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import router as router_module
from fastapi.testclient import TestClient


def _client(backend: str = "local") -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend=backend))


def _service(client: TestClient):
    return client.app.state.service  # type: ignore[attr-defined]


def test_get_next_step_is_null_until_one_is_set() -> None:
    client = _client()

    response = client.get("/api/next-step")

    assert response.status_code == 200
    assert response.json() is None


def test_post_next_step_records_it_and_get_reads_it_back() -> None:
    client = _client()

    created = client.post("/api/next-step", json={"text": "Talk to two support leads"})

    assert created.status_code == 200, created.text
    assert created.json()["text"] == "Talk to two support leads"
    assert client.get("/api/next-step").json()["id"] == created.json()["id"]


def test_post_next_step_refuses_an_empty_promise() -> None:
    client = _client()

    blank = client.post("/api/next-step", json={"text": "   "})

    assert blank.status_code == 400
    assert blank.json()["error"]["code"] == "validation"


def test_a_second_step_supersedes_the_first_and_get_reads_only_the_newest() -> None:
    client = _client()
    first = client.post("/api/next-step", json={"text": "Talk to two support leads"}).json()
    client.post("/api/next-step", json={"text": "Ask the payer what they do today"})

    open_step = client.get("/api/next-step").json()

    assert open_step["text"] == "Ask the payer what they do today"
    # The replaced promise is kept as history, and says plainly that it was replaced.
    stored = _service(client).repo.get_next_step(first["id"])
    assert stored is not None and stored.superseded_at is not None and stored.is_open is False


def test_resolve_answers_the_step_and_leaves_the_answer_in_the_library() -> None:
    client = _client()
    step = client.post("/api/next-step", json={"text": "Talk to two support leads"}).json()

    record = client.post(
        f"/api/next-step/{step['id']}/resolve",
        json={"resolution": "Both still hand-carry the spreadsheet"},
    )

    assert record.status_code == 200, record.text
    assert record.json()["content"] == "Both still hand-carry the spreadsheet"
    assert record.json()["raw"]["next_step_id"] == step["id"]
    assert record.json()["source_kind"] == "manual"
    assert client.get("/api/next-step").json() is None
    library = client.get("/api/evidence").json()["result"]
    assert [item["id"] for item in library if item["raw"].get("next_step_id") == step["id"]] == [
        record.json()["id"]
    ]


def test_resolve_needs_something_to_say() -> None:
    client = _client()
    step = client.post("/api/next-step", json={"text": "Draft the screener"}).json()

    blank = client.post(f"/api/next-step/{step['id']}/resolve", json={"resolution": " "})

    assert blank.status_code == 400
    assert _service(client).repo.get_next_step(step["id"]).is_open is True  # type: ignore[union-attr]


def test_patch_says_what_changed_and_keeping_is_not_a_change() -> None:
    """``keep`` is deliberately not a route action: "not yet" writes nothing.

    The aside offers it, the store stays as it was, and a route that recorded a
    no-op would be pretending the product learned something it did not.
    """
    client = _client()
    step = client.post("/api/next-step", json={"text": "Draft the interview guide"}).json()

    kept = client.patch(f"/api/next-step/{step['id']}", json={"action": "keep"})

    assert kept.status_code == 400
    assert kept.json()["error"]["code"] == "validation"
    assert client.get("/api/next-step").json()["id"] == step["id"]


def test_patch_reschedule_sets_when_to_ask_again() -> None:
    client = _client()
    step = client.post("/api/next-step", json={"text": "Draft the interview guide"}).json()
    later = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    rescheduled = client.patch(
        f"/api/next-step/{step['id']}", json={"action": "reschedule", "due_at": later}
    )

    assert rescheduled.status_code == 200, rescheduled.text
    assert rescheduled.json()["due_at"] is not None
    assert rescheduled.json()["due_at"] > rescheduled.json()["created_at"]


def test_patch_reschedule_without_a_when_is_refused() -> None:
    client = _client()
    step = client.post("/api/next-step", json={"text": "Draft the interview guide"}).json()

    missing = client.patch(f"/api/next-step/{step['id']}", json={"action": "reschedule"})

    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "validation"


def test_patch_drop_closes_the_step_without_inventing_an_answer() -> None:
    client = _client()
    step = client.post("/api/next-step", json={"text": "Draft the interview guide"}).json()

    dropped = client.patch(f"/api/next-step/{step['id']}", json={"action": "drop"})

    assert dropped.status_code == 200, dropped.text
    assert dropped.json()["superseded_at"] is not None
    assert client.get("/api/next-step").json() is None
    assert client.get("/api/evidence").json()["result"] == []


def test_patch_an_unknown_step_is_a_404_not_a_stack_trace() -> None:
    client = _client()

    missing = client.patch("/api/next-step/not-a-step", json={"action": "keep"})

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_mcp_backend_forwards_the_reads_and_writes(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []
    step = {
        "id": "ns-1",
        "text": "Talk to two support leads",
        "created_at": "2026-01-01T00:00:00+00:00",
        "due_at": None,
        "resolved_at": None,
        "resolution": None,
        "superseded_at": None,
        "outcome_id": None,
    }

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((tool, arguments))
        if tool == "get_next_step":
            return "null"
        return json.dumps(step)

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    client = _client(backend="mcp")

    assert client.get("/api/next-step?mcp_url=http://mcp").json() is None
    assert client.post("/api/next-step", json={"text": "x", "mcp_url": "http://mcp"}).json() == step
    assert (
        client.patch("/api/next-step/ns-1", json={"action": "drop", "mcp_url": "http://mcp"}).json()
        == step
    )
    assert calls == [
        ("get_next_step", {}),
        ("set_next_step", {"text": "x"}),
        ("drop_next_step", {"step_id": "ns-1"}),
    ]


def test_mcp_backend_requires_mcp_url_with_the_existing_400_shape() -> None:
    client = _client(backend="mcp")

    assert client.get("/api/next-step").status_code == 400
