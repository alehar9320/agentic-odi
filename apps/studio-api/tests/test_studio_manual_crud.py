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


def test_outcome_accepts_and_returns_sample_metadata() -> None:
    client = _client()
    job = client.post("/api/jobs", json={"name": "Ship a service"}).json()

    created = client.post(
        "/api/outcomes",
        json={
            "mcp_url": "",
            "job_id": job["id"],
            "statement": "Minimize the time it takes to deploy when releasing",
            "importance": 8.0,
            "satisfaction": 4.0,
            "importance_n": 40,
            "satisfaction_n": 40,
            "score_method": "survey",
        },
    )

    assert created.status_code == 200
    body = created.json()
    assert body["score_method"] == "survey"
    assert body["importance_n"] == 40
    assert body["satisfaction_n"] == 40


def test_outcome_defaults_to_an_estimate() -> None:
    client = _client()
    job = client.post("/api/jobs", json={"name": "Ship a service"}).json()

    created = client.post(
        "/api/outcomes",
        json={
            "mcp_url": "",
            "job_id": job["id"],
            "statement": "Minimize the time it takes to deploy when releasing",
            "importance": 8.0,
            "satisfaction": 4.0,
        },
    )

    assert created.status_code == 200
    assert created.json()["score_method"] == "estimate"
    assert created.json()["importance_n"] is None


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


def test_outcome_history_records_each_accepted_change() -> None:
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
            "note": "first pass",
        },
    ).json()

    client.patch(
        f"/api/outcomes/{outcome['id']}",
        json={"satisfaction": 6.0, "note": "after the review"},
    )

    history = client.get(f"/api/outcomes/{outcome['id']}/history").json()["result"]

    assert [row["satisfaction"] for row in history] == [4.0, 6.0]
    assert [row["note"] for row in history] == ["first pass", "after the review"]
    assert all(row["outcome_id"] == outcome["id"] for row in history)


def test_outcome_history_for_a_missing_outcome_is_404() -> None:
    response = _client().get("/api/outcomes/does-not-exist/history")
    assert response.status_code == 404


def test_outcome_note_is_snapshot_metadata_not_a_record_field() -> None:
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

    edited = client.patch(f"/api/outcomes/{outcome['id']}", json={"note": "why not"})

    assert edited.status_code == 200
    assert "note" not in edited.json()
