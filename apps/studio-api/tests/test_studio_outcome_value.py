"""W1/ALH-64: PUT /api/outcomes/{id}/value records what an opportunity is worth.

Readiness choices pinned here:

* The route is a thin adapter over one ``set_outcome_value`` call; it never
  derives a value from the score.
* A ``market`` or ``pilot`` basis without a ``source`` is a 422 (the shared error
  body), and nothing is written.
* Omitting ``estimate`` clears the value and its companions.
* A missing estimate stays ``null`` in the response — never ``0``.
"""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend="local"))


def _seed(client: TestClient) -> tuple[str, str]:
    job = client.post("/api/jobs", json={"name": "Publish a plugin"}).json()
    outcome = client.post(
        "/api/outcomes",
        json={
            "mcp_url": "",
            "job_id": job["id"],
            "statement": "Minimize the time it takes to publish a plugin when a release is ready",
            "importance": 9.0,
            "satisfaction": 3.0,
        },
    ).json()
    return job["id"], outcome["id"]


def test_value_records_a_market_estimate_with_its_source():
    client = _client()
    _, outcome_id = _seed(client)
    response = client.patch(
        f"/api/outcomes/{outcome_id}/value",
        json={
            "estimate": 250000.0,
            "unit": "currency",
            "basis": "market",
            "source": "Gartner 2025 plugin market report",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["value_estimate"] == 250000.0
    assert body["value_unit"] == "currency"
    assert body["value_basis"] == "market"
    assert body["value_source"] == "Gartner 2025 plugin market report"


def test_value_never_derives_from_the_score():
    client = _client()
    _, outcome_id = _seed(client)
    body = client.patch(
        f"/api/outcomes/{outcome_id}/value",
        json={"estimate": 4.0, "unit": "users"},
    ).json()
    assert body["value_estimate"] == 4.0
    assert body["opportunity_score"] == 15.0


def test_a_market_basis_without_a_source_is_refused_and_writes_nothing():
    client = _client()
    _, outcome_id = _seed(client)
    response = client.patch(
        f"/api/outcomes/{outcome_id}/value",
        json={"estimate": 1.0, "unit": "currency", "basis": "market"},
    )
    # The service refuses it as a contract violation (400), matching the CLI and
    # MCP surfaces; schema-level failures are the only 422s.
    assert response.status_code == 400
    assert "value_source" in response.text
    # Nothing was written: a fresh read still shows no estimate.
    canvas = client.get("/api/canvas").json()
    (outcome,) = [o for o in canvas["outcomes"] if o["id"] == outcome_id]
    assert outcome["value_estimate"] is None


def test_clearing_the_estimate_nulls_the_companions():
    client = _client()
    _, outcome_id = _seed(client)
    client.patch(
        f"/api/outcomes/{outcome_id}/value",
        json={
            "estimate": 100.0,
            "unit": "currency",
            "basis": "pilot",
            "n": 4,
            "source": "beta cohort",
        },
    )
    cleared = client.patch(f"/api/outcomes/{outcome_id}/value", json={"estimate": None})
    assert cleared.status_code == 200
    body = cleared.json()
    assert body["value_estimate"] is None
    assert body["value_unit"] is None
    assert body["value_n"] is None
    assert body["value_source"] is None


def test_an_unknown_outcome_is_a_404():
    response = _client().patch("/api/outcomes/nope/value", json={"estimate": 1.0, "unit": "users"})
    assert response.status_code == 404


def test_a_negative_estimate_is_refused_by_the_schema():
    client = _client()
    _, outcome_id = _seed(client)
    response = client.patch(
        f"/api/outcomes/{outcome_id}/value",
        json={"estimate": -1.0, "unit": "users"},
    )
    assert response.status_code == 422
