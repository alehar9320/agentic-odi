"""Router tests for the batch scoring endpoint (A9 / ALH-22).

``POST /api/outcomes/score-batch`` takes a bare list of
``{outcome_id, importance, satisfaction, why?}`` and returns one result per
item, in order. Each item goes through ``ODIService.update_outcome``, so the
1–10 bounds and the opportunity recompute are the service's, not the route's.
A bad row fails only itself: the rest of the batch still lands.
"""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository, ODIService, Outcome
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient

VALID = "Minimize the time it takes to onboard when a new hire starts"


def _client_with_outcomes(count: int) -> tuple[TestClient, ODIService, list[str]]:
    repo = InMemoryRepository()
    service = ODIService(repo)
    client = TestClient(create_app(repo, backend="local"))
    job = service.add_job("Onboard")
    ids = [
        service.add_outcome(job.id, VALID, importance=5.0, satisfaction=5.0).id
        for _ in range(count)
    ]
    return client, service, ids


def _stored(service: ODIService, outcome_id: str) -> Outcome:
    outcome = service.get_outcome(outcome_id)
    assert outcome is not None
    return outcome


def test_scoring_three_of_five_leaves_two_unscored() -> None:
    client, service, ids = _client_with_outcomes(5)

    response = client.post(
        "/api/outcomes/score-batch",
        json=[
            {"outcome_id": ids[0], "importance": 9, "satisfaction": 3},
            {"outcome_id": ids[1], "importance": 8, "satisfaction": 2},
            {"outcome_id": ids[2], "importance": 7, "satisfaction": 4},
        ],
    )

    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert [item["ok"] for item in results] == [True, True, True]
    assert _stored(service, ids[0]).opportunity_score == 15.0
    # The two outcomes that were not in the batch keep their scores untouched.
    assert _stored(service, ids[3]).importance == 5.0
    assert _stored(service, ids[4]).satisfaction == 5.0


def test_one_bad_row_fails_only_itself() -> None:
    client, service, ids = _client_with_outcomes(3)

    response = client.post(
        "/api/outcomes/score-batch",
        json=[
            {"outcome_id": ids[0], "importance": 9, "satisfaction": 3},
            {"outcome_id": ids[1], "importance": 11, "satisfaction": 3},
            {"outcome_id": ids[2], "importance": 6, "satisfaction": 2},
        ],
    )

    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert [item["ok"] for item in results] == [True, False, True]
    assert "between 1.0 and 10.0" in results[1]["error"]
    # The out-of-range row wrote nothing; the rows around it both landed.
    assert _stored(service, ids[1]).importance == 5.0
    assert _stored(service, ids[0]).opportunity_score == 15.0
    assert _stored(service, ids[2]).opportunity_score == 10.0


def test_a_missing_outcome_id_fails_that_item_only() -> None:
    client, service, ids = _client_with_outcomes(2)

    response = client.post(
        "/api/outcomes/score-batch",
        json=[
            {"outcome_id": "no-such-outcome", "importance": 9, "satisfaction": 3},
            {"outcome_id": ids[0], "importance": 9, "satisfaction": 3},
        ],
    )

    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert results[0]["ok"] is False
    assert results[1]["ok"] is True
    assert _stored(service, ids[0]).importance == 9.0


def test_each_result_correlates_with_its_input_and_echoes_why() -> None:
    client, _, ids = _client_with_outcomes(2)

    response = client.post(
        "/api/outcomes/score-batch",
        json=[
            {"outcome_id": ids[0], "importance": 9, "satisfaction": 3, "why": "setup drags"},
            {"outcome_id": ids[1], "importance": 4, "satisfaction": 6},
        ],
    )

    results = response.json()["results"]
    assert results[0]["outcome_id"] == ids[0]
    assert results[0]["why"] == "setup drags"
    assert results[0]["importance"] == 9
    assert results[1]["outcome_id"] == ids[1]
    assert "why" not in results[1]


def test_a_null_pair_restores_the_unscored_state() -> None:
    client, service, ids = _client_with_outcomes(1)

    response = client.post(
        "/api/outcomes/score-batch",
        json=[{"outcome_id": ids[0], "importance": None, "satisfaction": None}],
    )

    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["ok"] is True
    restored = _stored(service, ids[0])
    assert restored.importance is None
    assert restored.satisfaction is None
    assert restored.opportunity_score is None


def test_an_empty_batch_returns_an_honest_empty_result() -> None:
    client, _, _ = _client_with_outcomes(1)

    response = client.post("/api/outcomes/score-batch", json=[])

    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True, "results": []}


def test_the_route_appears_in_the_openapi_contract() -> None:
    client, _, _ = _client_with_outcomes(1)

    paths = client.get("/api/openapi.json").json()["paths"]

    assert "/api/outcomes/score-batch" in paths


def test_score_batch_is_the_only_scoring_route() -> None:
    client, _, _ = _client_with_outcomes(1)

    paths = client.get("/api/openapi.json").json()["paths"]
    scoring = sorted(path for path in paths if "score" in path)

    # A second scoring endpoint would give the CLI and the Studio two truths.
    assert scoring == ["/api/outcomes/score-batch"]
