"""Manual CRUD endpoints: the Studio must work without a model."""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend="local"))


def test_job_can_be_created_renamed_and_deleted_by_hand() -> None:
    client = _client()

    created = client.post("/api/jobs", json={"name": "Ship a service", "description": "Platform"})
    assert created.status_code == 200
    job = created.json()
    job_id = job["id"]
    assert job["name"] == "Ship a service"

    renamed = client.patch(f"/api/jobs/{job_id}", json={"name": "Ship a service safely"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Ship a service safely"

    removed = client.delete(f"/api/jobs/{job_id}")
    assert removed.status_code == 200
    assert removed.json() == {"deleted": job_id}
    assert client.get("/api/canvas").json()["jobs"] == []


def test_missing_job_returns_404() -> None:
    response = _client().patch("/api/jobs/does-not-exist", json={"name": "Nope"})
    assert response.status_code == 404


def test_step_can_be_edited_and_removed() -> None:
    client = _client()
    job = client.post("/api/jobs", json={"name": "Ship a service"}).json()
    # An outcome must exist before steps can be added.
    client.post(
        "/api/outcomes",
        json={
            "mcp_url": "",
            "job_id": job["id"],
            "statement": "Minimize the time it takes to deploy when releasing",
            "importance": 8.0,
            "satisfaction": 4.0,
        },
    )
    step = client.post(
        "/api/steps",
        json={"mcp_url": "", "job_id": job["id"], "name": "Prepare", "order": 3},
    ).json()
    step_id = step["id"]

    edited = client.patch(f"/api/steps/{step_id}", json={"name": "Prepare payload", "order": 2})
    assert edited.status_code == 200
    assert edited.json()["name"] == "Prepare payload"

    assert client.delete(f"/api/steps/{step_id}").status_code == 200
    assert client.get("/api/canvas").json()["steps"] == []


def test_outcome_scores_recompute_on_edit_and_delete() -> None:
    client = _client()
    job = client.post("/api/jobs", json={"name": "Ship a service"}).json()
    outcome = client.post(
        "/api/outcomes",
        json={
            "mcp_url": "",
            "job_id": job["id"],
            "statement": "Minimize the time to ship a release when the build is green",
            "importance": 8.0,
            "satisfaction": 4.0,
        },
    ).json()

    outcome_id = outcome["id"]

    edited = client.patch(
        f"/api/outcomes/{outcome_id}", json={"importance": 9.0, "satisfaction": 3.0}
    )
    assert edited.status_code == 200
    assert edited.json()["opportunity_score"] == 15.0

    assert client.delete(f"/api/outcomes/{outcome_id}").status_code == 200
    assert client.get("/api/canvas").json()["outcomes"] == []


def test_out_of_range_scores_are_rejected() -> None:
    client = _client()
    job = client.post("/api/jobs", json={"name": "Ship a service"}).json()
    outcome = client.post(
        "/api/outcomes",
        json={
            "mcp_url": "",
            "job_id": job["id"],
            "statement": "Minimize the time to ship a release when the build is green",
            "importance": 8.0,
            "satisfaction": 4.0,
        },
    ).json()

    outcome_id = outcome["id"]

    response = client.patch(f"/api/outcomes/{outcome_id}", json={"importance": 42})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "out_of_range"


def test_step_stage_round_trips_and_is_reported_by_the_map() -> None:
    client = _client()
    job = client.post("/api/jobs", json={"name": "Ship a service"}).json()
    client.post(
        "/api/outcomes",
        json={
            "mcp_url": "",
            "job_id": job["id"],
            "statement": "Minimize the time it takes to deploy when releasing",
            "importance": 8.0,
            "satisfaction": 4.0,
        },
    )

    created = client.post(
        "/api/steps",
        json={
            "mcp_url": "",
            "job_id": job["id"],
            "name": "Prepare",
            "order": 3,
            "stage": "prepare",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["stage"] == "prepare"
    assert created.json()["stage_index"] == 3

    mapped = client.get("/api/steps", params={"job_id": job["id"]}).json()
    step = next(s for s in mapped["result"] if s["id"] == created.json()["id"])
    assert step["stage"] == "prepare"


def test_step_order_that_disagrees_with_stage_is_rejected() -> None:
    client = _client()
    job = client.post("/api/jobs", json={"name": "Ship a service"}).json()
    client.post(
        "/api/outcomes",
        json={
            "mcp_url": "",
            "job_id": job["id"],
            "statement": "Minimize the time it takes to deploy when releasing",
            "importance": 8.0,
            "satisfaction": 4.0,
        },
    )

    created = client.post(
        "/api/steps",
        json={
            "mcp_url": "",
            "job_id": job["id"],
            "name": "Prepare",
            "order": 3,
            "stage": "prepare",
        },
    )
    step_id = created.json()["id"]

    # Moving the order without moving the stage is a contradiction.
    moved = client.patch(f"/api/steps/{step_id}", json={"order": 5})

    assert moved.status_code == 400, moved.text
    assert "order=5" in moved.json()["error"]["message"]
