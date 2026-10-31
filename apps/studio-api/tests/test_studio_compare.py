"""C3 (ALH-34): the side-by-side comparison endpoint.

Readiness choices pinned here:

* ``GET /api/compare?outcome_ids=a,b,c`` takes the ids explicitly, so the
  surface cannot silently compare a different set than the one the user saw.
* Two and three ids are accepted in the caller's order; fewer than two or more
  than three are refused with a message naming the limit, before any partial
  response is built.
* A missing metric renders the literal ``not measured``; a real recorded ``0``
  stays ``0``.
* Reads leave repository state unchanged.
"""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def _client() -> tuple[TestClient, InMemoryRepository]:
    repo = InMemoryRepository()
    return TestClient(create_app(repo, backend="local")), repo


def _seed(repo: InMemoryRepository) -> list[str]:
    from agentic_odi_core import ODIService

    service = ODIService(repo)
    job = service.add_job("Publish a plugin")
    ids = []
    for statement, importance, satisfaction in (
        ("Minimize the time it takes to publish a plugin when a release is ready", 8.0, 3.0),
        ("Minimize the cost of supporting a plugin when it ships", 9.0, 6.0),
        (
            "Minimize the number of steps it takes to publish a plugin when a release is ready",
            6.0,
            5.0,
        ),
    ):
        ids.append(service.add_outcome(job.id, statement, importance, satisfaction).id)
    return ids


def test_compare_returns_aligned_rows_for_two_ids() -> None:
    client, repo = _client()
    ids = _seed(repo)

    response = client.get("/api/compare", params={"outcome_ids": ",".join(ids[:2])})

    assert response.status_code == 200
    body = response.json()
    assert body["columns"] == ids[:2]
    for row in body["rows"]:
        assert len(row["cells"]) == 2


def test_compare_keeps_the_given_column_order() -> None:
    client, repo = _client()
    ids = _seed(repo)

    response = client.get("/api/compare", params={"outcome_ids": f"{ids[2]},{ids[0]}"})

    assert response.json()["columns"] == [ids[2], ids[0]]


def test_compare_accepts_three_ids() -> None:
    client, repo = _client()
    ids = _seed(repo)

    response = client.get("/api/compare", params={"outcome_ids": ",".join(ids)})

    assert response.status_code == 200
    assert len(response.json()["columns"]) == 3


def test_compare_refuses_a_fourth_id_naming_the_limit() -> None:
    client, repo = _client()
    ids = _seed(repo)

    response = client.get("/api/compare", params={"outcome_ids": ",".join([*ids, ids[0]])})

    assert response.status_code == 400
    assert "at most 3" in response.json()["error"]["message"]


def test_compare_refuses_a_single_id() -> None:
    client, repo = _client()
    ids = _seed(repo)

    response = client.get("/api/compare", params={"outcome_ids": ids[0]})

    assert response.status_code == 400
    assert "at least 2" in response.json()["error"]["message"]


def test_compare_refuses_an_empty_request() -> None:
    client, _ = _client()

    response = client.get("/api/compare", params={"outcome_ids": ""})

    assert response.status_code == 400


def test_compare_refuses_a_duplicate_id() -> None:
    client, repo = _client()
    ids = _seed(repo)

    response = client.get("/api/compare", params={"outcome_ids": f"{ids[0]},{ids[0]}"})

    assert response.status_code == 400
    assert "distinct" in response.json()["error"]["message"]


def test_compare_refuses_an_unknown_id() -> None:
    client, repo = _client()
    ids = _seed(repo)

    response = client.get("/api/compare", params={"outcome_ids": f"{ids[0]},does-not-exist"})

    assert response.status_code == 404


def test_compare_renders_not_measured_for_a_missing_metric() -> None:
    from agentic_odi_core import ODIService, Outcome

    client, repo = _client()
    service = ODIService(repo)
    job = service.add_job("Publish a plugin")
    scored = service.add_outcome(
        job.id, "Minimize the time it takes to publish a plugin when a release is ready", 8.0, 3.0
    )
    unscored = repo.add_outcome(
        Outcome(
            job_id=job.id,
            statement="Minimize the number of steps it takes to publish a plugin when a release is ready",
        )
    )

    response = client.get("/api/compare", params={"outcome_ids": f"{scored.id},{unscored.id}"})

    score = next(row for row in response.json()["rows"] if row["metric"] == "score")
    assert score["cells"] == ["13", "not measured"]


def test_compare_leaves_repository_state_unchanged() -> None:
    client, repo = _client()
    ids = _seed(repo)
    before = dict(repo.outcomes)

    client.get("/api/compare", params={"outcome_ids": ",".join(ids)})

    assert repo.outcomes == before
