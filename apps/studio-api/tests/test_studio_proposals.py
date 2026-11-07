"""The proposal routes: mine evidence, review it, approve or reject it."""

from __future__ import annotations

from typing import Any

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient

COMPLAINT = "It takes too long to rotate production secrets before the next deploy."


def _client() -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend="local"))


def _job(client: TestClient) -> str:
    return client.post("/api/jobs", json={"name": "Ship a service"}).json()["id"]


def _capture(client: TestClient, job_id: str, **overrides: Any) -> dict:
    payload: dict[str, Any] = {
        "source_name": "gong",
        "source_kind": "mcp",
        "name": "Fintech call",
        "content": COMPLAINT,
        "job_id": job_id,
    }
    payload.update(overrides)
    response = client.post("/api/evidence", json=payload)
    assert response.status_code == 200
    return response.json()["result"]


def _proposal(client: TestClient) -> tuple[str, dict]:
    job_id = _job(client)
    record = _capture(client, job_id)
    proposed = client.post("/api/proposals", json={"evidence_id": record["id"]})
    assert proposed.status_code == 200
    return job_id, proposed.json()["result"]


def test_proposal_lists_only_what_is_still_pending() -> None:
    client = _client()
    _job_id, proposal = _proposal(client)

    assert proposal["status"] == "proposed"
    assert proposal["statement"].startswith("Minimize")
    assert proposal["confidence"] > 0
    assert [
        item["id"] for item in client.get("/api/proposals?status=proposed").json()["result"]
    ] == [proposal["id"]]
    assert client.get("/api/proposals?status=approved").json()["result"] == []


def test_approving_a_proposal_writes_an_outcome_on_its_job() -> None:
    client = _client()
    job_id, proposal = _proposal(client)

    approved = client.post(f"/api/proposals/{proposal['id']}/approve", json={})

    assert approved.status_code == 200
    outcome = approved.json()["result"]
    assert outcome["job_id"] == job_id
    assert outcome["statement"] == proposal["statement"]
    stored = client.get(f"/api/outcomes?job_id={job_id}").json()["result"]
    assert [item["statement"] for item in stored] == [proposal["statement"]]
    assert client.get("/api/proposals?status=proposed").json()["result"] == []


def test_editing_on_approval_validates_the_statement() -> None:
    client = _client()
    _job_id, proposal = _proposal(client)

    rejected_edit = client.post(
        f"/api/proposals/{proposal['id']}/approve",
        json={"statement": "Rotate secrets faster"},
    )
    assert rejected_edit.status_code >= 400

    approved = client.post(
        f"/api/proposals/{proposal['id']}/approve",
        json={
            "statement": "Minimize the time it takes to rotate production secrets before a deploy",
            "importance": 9.0,
            "satisfaction": 2.0,
        },
    )
    assert approved.status_code == 200
    assert approved.json()["result"]["importance"] == 9.0


def test_rejecting_a_proposal_writes_nothing() -> None:
    client = _client()
    job_id, proposal = _proposal(client)

    rejected = client.post(f"/api/proposals/{proposal['id']}/reject", json={})

    assert rejected.status_code == 200
    assert rejected.json()["result"]["status"] == "rejected"
    assert client.get(f"/api/outcomes?job_id={job_id}").json()["result"] == []


def test_an_unknown_status_is_refused_rather_than_ignored() -> None:
    client = _client()

    response = client.get("/api/proposals?status=pending")

    assert response.status_code == 422
