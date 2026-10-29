"""The evidence routes: capture with a link, promote it, delete it."""

from __future__ import annotations

from typing import Any

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient

LINK = "https://app.gong.io/calls/104"
STATEMENT = "Minimize the time it takes to sync a secret across environments when rotating keys"


def _client() -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend="local"))


def _job(client: TestClient) -> str:
    return client.post("/api/jobs", json={"name": "Ship a service"}).json()["id"]


def _capture(client: TestClient, job_id: str, **overrides: Any) -> dict:
    payload: dict[str, Any] = {
        "source_name": "gong",
        "source_kind": "mcp",
        "name": "Fintech call",
        "content": "A junior engineer broke staging because the Stripe secret was not copied.",
        "job_id": job_id,
    }
    payload.update(overrides)
    response = client.post("/api/evidence", json=payload)
    assert response.status_code == 200
    return response.json()["result"]


def test_evidence_keeps_the_link_back_to_the_record_it_came_from() -> None:
    client = _client()
    record = _capture(client, _job(client), url=LINK)

    assert record["url"] == LINK
    assert [item["url"] for item in client.get("/api/canvas").json()["evidence"]] == [LINK]


def test_evidence_without_a_link_is_still_a_valid_record() -> None:
    client = _client()
    record = _capture(client, _job(client))

    assert record["url"] is None
    assert record["name"] == "Fintech call"


def test_evidence_promotes_into_an_outcome_on_its_job() -> None:
    client = _client()
    job_id = _job(client)
    record = _capture(client, job_id, url=LINK)

    promoted = client.post(
        f"/api/evidence/{record['id']}/promote",
        json={
            "target": "outcome",
            "statement": STATEMENT,
            "importance": 8.0,
            "satisfaction": 3.0,
        },
    )

    assert promoted.status_code == 200
    assert promoted.json()["result"]["job_id"] == job_id
    assert promoted.json()["result"]["importance"] == 8.0
    assert [item["statement"] for item in client.get("/api/canvas").json()["outcomes"]] == [
        STATEMENT
    ]


def test_evidence_promotes_into_a_job() -> None:
    client = _client()
    record = _capture(client, _job(client))

    promoted = client.post(
        f"/api/evidence/{record['id']}/promote",
        json={"target": "job", "name": "Sync secrets"},
    )

    assert promoted.status_code == 200
    assert promoted.json()["result"]["name"] == "Sync secrets"
    assert "Sync secrets" in [job["name"] for job in client.get("/api/canvas").json()["jobs"]]


def test_deleting_evidence_removes_it_from_the_canvas() -> None:
    client = _client()
    record = _capture(client, _job(client), url=LINK)

    removed = client.delete(f"/api/evidence/{record['id']}")

    assert removed.status_code == 200
    assert client.get("/api/canvas").json()["evidence"] == []


def test_missing_evidence_answers_404_with_a_way_out() -> None:
    client = _client()

    removed = client.delete("/api/evidence/does-not-exist")
    promoted = client.post(
        "/api/evidence/does-not-exist/promote", json={"target": "job", "name": "Nope"}
    )

    assert removed.status_code == 404
    assert promoted.status_code == 404
    assert "list_evidence" in removed.json()["error"]["message"]
