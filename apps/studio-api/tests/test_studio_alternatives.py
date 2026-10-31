"""Alternatives CRUD and the three-state solution query through the Studio API (M2-07)."""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend="local"))


def _job_and_outcome(client: TestClient) -> tuple[str, str]:
    job_id = client.post("/api/jobs", json={"name": "Ship a service"}).json()["id"]
    outcome = client.post(
        "/api/outcomes",
        json={
            "mcp_url": "",
            "job_id": job_id,
            "statement": "Minimize the time it takes to ship when a release is cut",
            "importance": 8.0,
            "satisfaction": 4.0,
        },
    ).json()
    return job_id, outcome["id"]


def _alternative(
    client: TestClient, job_id: str, *, name: str = "Spreadsheet", kind: str = "manual"
) -> dict:
    response = client.post(
        "/api/alternatives",
        json={"job_id": job_id, "name": name, "kind": kind},
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]


def test_a_linked_spreadsheet_reports_yes() -> None:
    client = _client()
    job_id, outcome_id = _job_and_outcome(client)
    alternative = _alternative(client, job_id)

    linked = client.post(
        f"/api/outcomes/{outcome_id}/alternatives",
        json={"alternative_id": alternative["id"], "adequacy": 7.0, "usage_n": 12},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["result"]["adequacy"] == 7.0

    pairs = client.get(f"/api/outcomes/{outcome_id}/alternatives").json()["result"]
    assert [pair["alternative"]["id"] for pair in pairs] == [alternative["id"]]

    verdict = client.get(f"/api/outcomes/{outcome_id}/existing-solution").json()["result"]
    assert verdict["existing_solution"] == "yes"


def test_nothing_only_reports_no_linked_nothing() -> None:
    client = _client()
    job_id, outcome_id = _job_and_outcome(client)
    alternative = _alternative(client, job_id, name="Nothing today", kind="nothing")
    client.post(
        f"/api/outcomes/{outcome_id}/alternatives",
        json={"alternative_id": alternative["id"], "adequacy": 1.0},
    )

    verdict = client.get(f"/api/outcomes/{outcome_id}/existing-solution").json()["result"]
    assert verdict["existing_solution"] == "no_linked_nothing"


def test_no_links_reports_no_link_at_all() -> None:
    client = _client()
    _, outcome_id = _job_and_outcome(client)

    verdict = client.get(f"/api/outcomes/{outcome_id}/existing-solution").json()["result"]
    assert verdict["existing_solution"] == "no_link_at_all"


def test_alternative_can_be_listed_fetched_and_deleted() -> None:
    client = _client()
    job_id, _ = _job_and_outcome(client)
    alternative = _alternative(client, job_id)

    listed = client.get("/api/alternatives", params={"job_id": job_id}).json()["result"]
    assert [item["id"] for item in listed] == [alternative["id"]]

    fetched = client.get(f"/api/alternatives/{alternative['id']}").json()["result"]
    assert fetched["name"] == "Spreadsheet"

    assert client.delete(f"/api/alternatives/{alternative['id']}").status_code == 200
    assert client.get(f"/api/alternatives/{alternative['id']}").status_code == 404


def test_unlink_removes_only_the_link() -> None:
    client = _client()
    job_id, outcome_id = _job_and_outcome(client)
    alternative = _alternative(client, job_id)
    client.post(
        f"/api/outcomes/{outcome_id}/alternatives",
        json={"alternative_id": alternative["id"], "adequacy": 7.0},
    )

    assert (
        client.delete(f"/api/outcomes/{outcome_id}/alternatives/{alternative['id']}").status_code
        == 200
    )
    assert client.get(f"/api/outcomes/{outcome_id}/alternatives").json()["result"] == []
    assert client.get(f"/api/alternatives/{alternative['id']}").status_code == 200


def test_an_unknown_alternative_is_404() -> None:
    client = _client()
    assert client.get("/api/alternatives/missing").status_code == 404
