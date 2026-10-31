"""Customer-outcome and evidence CRUD through the Studio API."""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient

CUSTOMER_VALUE = {
    "direction": "minimize",
    "unit_of_measure": "minutes",
    "object_of_control": "the time it takes to ship",
    "statement": "Minimize the time it takes to ship",
    "importance": 8.5,
    "satisfaction": 3.5,
}

BUSINESS_VALUE = {
    "category": "revenue_growth",
    "statement": "Faster releases unlock more deals",
}


def _client() -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend="local"))


def _job_id(client: TestClient) -> str:
    return client.post("/api/jobs", json={"name": "Ship a service"}).json()["id"]


def _customer_outcome(client: TestClient, job_id: str) -> dict:
    response = client.post(
        "/api/customer-outcomes",
        json={
            "job_id": job_id,
            "customer_value": CUSTOMER_VALUE,
            "business_value": BUSINESS_VALUE,
        },
    )
    assert response.status_code == 200
    return response.json()["result"]


def test_customer_outcome_can_be_created_read_updated_and_deleted() -> None:
    client = _client()
    job_id = _job_id(client)

    created = _customer_outcome(client, job_id)
    assert created["customer_value"]["statement"] == "Minimize the time it takes to ship"
    assert created["opportunity_score"] > 0

    listed = client.get("/api/customer-outcomes", params={"job_id": job_id})
    assert [item["id"] for item in listed.json()["result"]] == [created["id"]]

    fetched = client.get(f"/api/customer-outcomes/{created['id']}")
    assert fetched.json()["result"]["id"] == created["id"]

    patched = client.patch(
        f"/api/customer-outcomes/{created['id']}",
        json={"customer_value": {**CUSTOMER_VALUE, "importance": 9.5}},
    )
    assert patched.status_code == 200
    assert patched.json()["result"]["customer_value"]["importance"] == 9.5

    assert client.delete(f"/api/customer-outcomes/{created['id']}").status_code == 200
    assert client.get(f"/api/customer-outcomes/{created['id']}").status_code == 404


def test_customer_outcome_for_an_unknown_job_is_404() -> None:
    response = _client().post(
        "/api/customer-outcomes",
        json={
            "job_id": "does-not-exist",
            "customer_value": CUSTOMER_VALUE,
            "business_value": BUSINESS_VALUE,
        },
    )

    assert response.status_code == 404


def test_customer_outcome_with_a_bad_score_is_422() -> None:
    client = _client()

    response = client.post(
        "/api/customer-outcomes",
        json={
            "job_id": _job_id(client),
            "customer_value": {**CUSTOMER_VALUE, "importance": 12},
            "business_value": BUSINESS_VALUE,
        },
    )

    assert response.status_code == 422


def _evidence(client: TestClient, job_id: str) -> dict:
    response = client.post(
        "/api/evidence",
        json={
            "source_name": "Gong",
            "source_kind": "mcp",
            "name": "Call with Acme",
            "content": "They lose a day to config drift.",
            "job_id": job_id,
        },
    )
    assert response.status_code == 200
    return response.json()["result"]


def test_evidence_can_be_created_listed_read_and_deleted() -> None:
    client = _client()
    job_id = _job_id(client)

    created = _evidence(client, job_id)
    assert created["name"] == "Call with Acme"
    assert created["item_type"] == "manual"

    listed = client.get("/api/evidence", params={"job_id": job_id})
    assert [item["id"] for item in listed.json()["result"]] == [created["id"]]

    assert client.get(f"/api/evidence/{created['id']}").json()["result"]["id"] == created["id"]

    assert client.delete(f"/api/evidence/{created['id']}").status_code == 200
    assert client.get(f"/api/evidence/{created['id']}").status_code == 404
    assert client.delete(f"/api/evidence/{created['id']}").status_code == 404
