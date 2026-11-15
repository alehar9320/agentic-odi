"""C7 / C7.2 (ALH-38, ALH-160): the roadmap derivation endpoint.

Readiness choices pinned here:

* ``GET /api/roadmap?job_id=...`` is a view over the decision log, not a store:
  entries are grouped by the quarter of the decision date in UTC.
* ``today`` pins the window so the response is reproducible; it defaults to the
  current UTC date when omitted.
* An undecided outcome is excluded and counted with its reason; a superseded
  decision contributes no rows.
* A baseline nobody measured is ``null`` — never ``0``.
* An unknown job is not a success, and a malformed ``today`` is a 422.
* Reads leave repository state unchanged.
"""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def _client() -> tuple[TestClient, InMemoryRepository]:
    repo = InMemoryRepository()
    return TestClient(create_app(repo, backend="local")), repo


def _seed(repo: InMemoryRepository) -> tuple[str, list[str]]:
    service = ODIService(repo)
    job = service.add_job("Publish a plugin")
    ids = [
        service.add_outcome(
            job.id,
            "Minimize the time it takes to publish a plugin when a release is ready",
            8.0,
            3.0,
        ).id,
        service.add_outcome(
            job.id, "Minimize the cost of supporting a plugin when it ships", 5.0, 7.0
        ).id,
    ]
    return job.id, ids


def _record(service: ODIService, job_id: str, outcome_id: str, decided_at: str) -> str:
    return service.record_decision(
        job_id=job_id,
        chosen_outcome_ids=[outcome_id],
        rationale="The publishing path blocks every release.",
        decided_by="dana",
        decided_at=decided_at,
    ).id


def test_roadmap_groups_by_quarter_and_counts_the_undecided():
    client, repo = _client()
    job_id, ids = _seed(repo)
    service = ODIService(repo)
    _record(service, job_id, ids[0], "2026-10-01T00:00:00Z")

    response = client.get("/api/roadmap", params={"job_id": job_id, "today": "2026-11-15"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert [entry["period"] for entry in body["entries"]] == ["2026-Q4"]
    assert body["entries"][0]["outcome_id"] == ids[0]
    assert body["entries"][0]["baseline"] is None
    assert body["entries"][0]["target"] is None
    assert body["undecided_count"] == 1
    assert "1 outcome(s) have no decision" in body["exclusion_note"]


def test_roadmap_empty_job_is_not_an_error():
    client, repo = _client()
    job_id, _ = _seed(repo)

    response = client.get("/api/roadmap", params={"job_id": job_id, "today": "2026-11-15"})

    assert response.status_code == 200
    body = response.json()
    assert body["entries"] == []
    assert body["undecided_count"] == 2
    assert "2 outcome(s) have no decision" in body["exclusion_note"]


def test_roadmap_superseded_decision_is_excluded_and_counted():
    client, repo = _client()
    job_id, ids = _seed(repo)
    service = ODIService(repo)
    first = _record(service, job_id, ids[0], "2026-10-01T00:00:00Z")
    service.record_decision(
        job_id=job_id,
        chosen_outcome_ids=[ids[1]],
        rationale="Support cost now dominates.",
        decided_by="dana",
        decided_at="2026-10-05T00:00:00Z",
        supersedes=first,
    )

    response = client.get("/api/roadmap", params={"job_id": job_id, "today": "2026-11-15"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert [entry["outcome_id"] for entry in body["entries"]] == [ids[1]]
    assert body["superseded_excluded_count"] == 1


def test_roadmap_missing_job_is_not_a_success():
    client, _ = _client()

    response = client.get("/api/roadmap", params={"job_id": "JOB-NOPE", "today": "2026-11-15"})

    assert response.status_code == 404
    assert "traceback" not in response.text.lower()


def test_roadmap_malformed_today_is_refused():
    client, repo = _client()
    job_id, _ = _seed(repo)

    response = client.get("/api/roadmap", params={"job_id": job_id, "today": "not-a-date"})

    assert response.status_code == 422


def test_roadmap_does_not_change_repository_state():
    client, repo = _client()
    job_id, ids = _seed(repo)
    service = ODIService(repo)
    _record(service, job_id, ids[0], "2026-10-01T00:00:00Z")
    before = len(repo.list_decisions(job_id, limit=None))

    client.get("/api/roadmap", params={"job_id": job_id, "today": "2026-11-15"})

    assert len(repo.list_decisions(job_id, limit=None)) == before
