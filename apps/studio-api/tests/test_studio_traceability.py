"""The traceability route and the alignment routes.

The report is read-only and honest about an empty vision; linking refuses text
the vision does not hold and names what it does.
"""

from __future__ import annotations

from agentic_odi_core import V2MOM, InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient

_METHOD = "Cut time-to-first-value"
_MEASURE = "Net revenue retention above 120%"


def _client() -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend="local"))


def _service(client: TestClient):
    return client.app.state.service  # type: ignore[attr-defined]


def _seed(client: TestClient, *, with_vision: bool = True) -> str:
    service = _service(client)
    if with_vision:
        service.save_v2mom(
            V2MOM(vision="Make onboarding painless", methods=[_METHOD], measures=[_MEASURE])
        )
    job = service.add_job("Onboard a new engineer")
    outcome = service.add_outcome(
        job.id,
        statement="Minimize the time it takes to onboard a new engineer when they join",
        importance=8,
        satisfaction=4,
    )
    return outcome.id


def test_an_empty_vision_says_there_is_nothing_to_check() -> None:
    response = _client().get("/api/traceability")

    assert response.status_code == 200
    body = response.json()
    assert body["objectives_defined"] is False
    assert "no objectives defined" in body["message"].lower()
    assert body["orphans"] == [] and body["unfunded"] == [] and body["drift"] == []


def test_linking_persists_and_the_report_counts_the_unfunded_objective() -> None:
    client = _client()
    outcome_id = _seed(client)

    linked = client.post(
        f"/api/outcomes/{outcome_id}/alignments", json={"field": "method", "text": _METHOD}
    )
    report = client.get("/api/traceability")
    alignments = client.get("/api/alignments")

    assert linked.status_code == 200
    assert linked.json()["trace"][0]["text"] == _METHOD
    assert alignments.json()[0]["outcome_id"] == outcome_id
    assert report.json()["counts"] == {"orphans": 0, "unfunded": 1, "drift": 0}
    assert report.json()["unfunded"][0]["text"] == _MEASURE


def test_linking_unknown_text_is_refused_with_the_entries_that_exist() -> None:
    client = _client()
    outcome_id = _seed(client)

    response = client.post(
        f"/api/outcomes/{outcome_id}/alignments", json={"field": "method", "text": "Something else"}
    )

    assert response.status_code == 400
    assert _METHOD in response.json()["error"]["message"]


def test_linking_an_unknown_outcome_is_a_404() -> None:
    client = _client()
    _seed(client)

    response = client.post(
        "/api/outcomes/nope/alignments", json={"field": "method", "text": _METHOD}
    )

    assert response.status_code == 404


def test_a_rejected_field_is_a_422() -> None:
    client = _client()
    outcome_id = _seed(client)

    response = client.post(
        f"/api/outcomes/{outcome_id}/alignments", json={"field": "vision", "text": _METHOD}
    )

    assert response.status_code == 422


def test_unlinking_returns_the_outcome_to_an_orphan() -> None:
    client = _client()
    outcome_id = _seed(client)
    linked = client.post(
        f"/api/outcomes/{outcome_id}/alignments", json={"field": "method", "text": _METHOD}
    ).json()
    key = linked["trace"][0]["key"]

    removed = client.delete(f"/api/outcomes/{outcome_id}/alignments/method/{key}")
    report = client.get("/api/traceability")

    assert removed.status_code == 200
    assert removed.json()["trace"] == []
    assert report.json()["orphans"] == [outcome_id]


def test_removing_a_method_leaves_drift_not_an_unlink() -> None:
    client = _client()
    outcome_id = _seed(client)
    client.post(f"/api/outcomes/{outcome_id}/alignments", json={"field": "method", "text": _METHOD})

    _service(client).save_v2mom(V2MOM(methods=["A different method"]))
    report = client.get("/api/traceability").json()

    assert report["counts"]["drift"] == 1
    assert report["drift"][0]["text"] == _METHOD
    assert report["orphans"] == []
