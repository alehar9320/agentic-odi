"""D1–D4 (ALH-40…ALH-43) at the Studio API surface.

Readiness choices pinned here:

* ``POST /api/segments`` validates membership through the shared service, so the
  route cannot accept a cross-job or missing member the CLI would refuse.
* ``GET /api/jobs/{id}/segment-candidates`` is read-only: suggesting twice
  leaves repository state unchanged.
* ``POST /api/segment-candidates/accept`` is the only write in the suggestion
  flow, and it targets exactly the fingerprint that was shown.
* ``GET /api/segments/{id}/profile`` keeps underserved and overserved separate
  and reports a ``None`` ratio when nothing is measured, never ``0.0``.
* ``POST /api/segments/{id}/strategy`` refuses a strategy the segment's data
  does not support, naming the missing condition.
* An unknown segment is a 404, not an empty profile.
"""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def _client() -> tuple[TestClient, InMemoryRepository]:
    repo = InMemoryRepository()
    return TestClient(create_app(repo, backend="local")), repo


def _statement(index: int) -> str:
    return f"Minimize the time it takes to publish plugin {index} when a release is ready"


def _seed(repo: InMemoryRepository, scores: list[tuple[float, float]]):
    """One job with one scored outcome per ``(importance, satisfaction)``."""
    service = ODIService(repo)
    job = service.add_job("Publish a plugin")
    outcomes = [
        service.add_outcome(job.id, _statement(i), importance, satisfaction)
        for i, (importance, satisfaction) in enumerate(scores)
    ]
    return service, job, outcomes


def test_post_segment_returns_the_created_segment() -> None:
    client, repo = _client()
    _, job, outcomes = _seed(repo, [(9.0, 3.0), (8.0, 4.0)])

    body = client.post(
        "/api/segments",
        json={
            "job_id": job.id,
            "name": "Release engineers",
            "criterion": "They own the publish step.",
            "outcome_ids": [o.id for o in outcomes],
        },
    ).json()

    assert body["name"] == "Release engineers"
    assert body["outcome_ids"] == [o.id for o in outcomes]
    assert body["origin"] == "manual"
    assert client.get(f"/api/segments?job_id={job.id}").json()[0]["id"] == body["id"]


def test_post_segment_refuses_a_cross_job_member() -> None:
    client, repo = _client()
    service, job, outcomes = _seed(repo, [(9.0, 3.0)])
    other_job = service.add_job("Ship a service")
    foreign = service.add_outcome(other_job.id, _statement(9), 9.0, 3.0)

    response = client.post(
        "/api/segments",
        json={
            "job_id": job.id,
            "name": "Mixed",
            "criterion": "Should be refused.",
            "outcome_ids": [outcomes[0].id, foreign.id],
        },
    )

    assert response.status_code == 400
    assert "different job" in response.text
    # The refusal happened before any write.
    assert client.get(f"/api/segments?job_id={job.id}").json() == []


def test_get_segment_profile_keeps_the_two_halves_separate() -> None:
    client, repo = _client()
    _, job, outcomes = _seed(repo, [(9.0, 3.0), (5.0, 9.0)])
    segment = client.post(
        "/api/segments",
        json={
            "job_id": job.id,
            "name": "Finance leads",
            "criterion": "They reconcile by hand.",
            "outcome_ids": [o.id for o in outcomes],
        },
    ).json()

    profile = client.get(f"/api/segments/{segment['id']}/profile").json()
    assert profile["total_members"] == 2
    assert profile["measured_count"] == 2
    assert profile["underserved_count"] == 1
    assert profile["overserved_count"] == 1
    assert profile["measured_ratio"] == 1.0
    assert len(profile["top_underserved"]) == 1
    assert len(profile["top_overserved"]) == 1


def test_profile_of_a_segment_with_no_measured_outcome_has_a_null_ratio() -> None:
    client, repo = _client()
    service = ODIService(repo)
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(job.id, _statement(1), 9.0, 3.0)
    # Clear the scores: an unscored member is not a zero-scored one.
    service.update_outcome(outcome.id, {"importance": None, "satisfaction": None})
    segment = client.post(
        "/api/segments",
        json={
            "job_id": job.id,
            "name": "Unscored group",
            "criterion": "No measurement yet.",
            "outcome_ids": [outcome.id],
        },
    ).json()

    profile = client.get(f"/api/segments/{segment['id']}/profile").json()
    assert profile["measured_ratio"] is None
    assert profile["measured_count"] == 0
    assert profile["unscored_count"] == 1
    assert any("scored" in gap for gap in profile["gaps"])


def test_an_unknown_segment_is_404_not_an_empty_profile() -> None:
    client, _ = _client()
    response = client.get("/api/segments/ghost/profile")
    assert response.status_code == 404
    assert "Traceback" not in response.text


def test_suggesting_twice_writes_nothing() -> None:
    client, repo = _client()
    _, job, _ = _seed(repo, [(9.0, 3.0), (9.0, 2.0), (9.0, 4.0)])

    first = client.get(f"/api/jobs/{job.id}/segment-candidates").json()
    before = (dict(repo.segments), list(repo.strategies))
    second = client.get(f"/api/jobs/{job.id}/segment-candidates").json()

    assert first == second
    assert (dict(repo.segments), list(repo.strategies)) == before
    assert first["candidates"]


def test_accepting_a_candidate_creates_exactly_one_segment() -> None:
    client, repo = _client()
    _, job, _ = _seed(repo, [(9.0, 3.0), (9.0, 2.0), (9.0, 4.0)])
    candidate = client.get(f"/api/jobs/{job.id}/segment-candidates").json()["candidates"][0]

    accepted = client.post(
        "/api/segment-candidates/accept",
        json={"job_id": job.id, "fingerprint": candidate["fingerprint"]},
    ).json()

    assert accepted["origin"] == "candidate"
    assert accepted["candidate_fingerprint"] == candidate["fingerprint"]
    assert accepted["outcome_ids"] == list(candidate["members"])
    assert len(client.get(f"/api/segments?job_id={job.id}").json()) == 1

    # Repeat acceptance is idempotent, not a second segment.
    again = client.post(
        "/api/segment-candidates/accept",
        json={"job_id": job.id, "fingerprint": candidate["fingerprint"]},
    ).json()
    assert again["id"] == accepted["id"]
    assert len(client.get(f"/api/segments?job_id={job.id}").json()) == 1


def test_a_stale_fingerprint_is_refused() -> None:
    client, repo = _client()
    _, job, _ = _seed(repo, [(9.0, 3.0), (9.0, 2.0), (9.0, 4.0)])
    response = client.post(
        "/api/segment-candidates/accept",
        json={"job_id": job.id, "fingerprint": "deadbeef"},
    )
    assert response.status_code == 400
    assert "stale" in response.text


def test_differentiated_strategy_needs_an_underserved_member() -> None:
    client, repo = _client()
    _, job, outcomes = _seed(repo, [(9.0, 3.0)])
    segment = client.post(
        "/api/segments",
        json={
            "job_id": job.id,
            "name": "Underserved",
            "criterion": "One underserved outcome.",
            "outcome_ids": [outcomes[0].id],
        },
    ).json()

    recorded = client.post(
        f"/api/segments/{segment['id']}/strategy",
        json={
            "kind": "differentiated",
            "rationale": "The gap is real.",
            "expected_effect": "Shorter publish time.",
        },
    ).json()
    assert recorded["kind"] == "differentiated"
    assert recorded["segment_id"] == segment["id"]
    assert len(client.get(f"/api/strategies?segment_id={segment['id']}").json()) == 1


def test_differentiated_strategy_is_refused_without_an_underserved_member() -> None:
    client, repo = _client()
    _, job, outcomes = _seed(repo, [(9.0, 9.0)])
    segment = client.post(
        "/api/segments",
        json={
            "job_id": job.id,
            "name": "Appropriate",
            "criterion": "Nothing underserved.",
            "outcome_ids": [outcomes[0].id],
        },
    ).json()

    response = client.post(
        f"/api/segments/{segment['id']}/strategy",
        json={
            "kind": "differentiated",
            "rationale": "Should be refused.",
            "expected_effect": "Nothing.",
        },
    )
    assert response.status_code == 400
    assert "underserved" in response.text
    assert client.get(f"/api/strategies?segment_id={segment['id']}").json() == []


def test_a_new_market_strategy_is_refused_while_alternatives_evidence_is_absent() -> None:
    client, repo = _client()
    _, job, outcomes = _seed(repo, [(9.0, 3.0)])
    segment = client.post(
        "/api/segments",
        json={
            "job_id": job.id,
            "name": "Group",
            "criterion": "Any group.",
            "outcome_ids": [outcomes[0].id],
        },
    ).json()

    response = client.post(
        f"/api/segments/{segment['id']}/strategy",
        json={
            "kind": "new_market",
            "rationale": "Nothing serves it.",
            "expected_effect": "New demand.",
        },
    )
    assert response.status_code == 400
    assert "alternatives" in response.text


def test_a_strategy_for_an_unknown_segment_is_404() -> None:
    client, _ = _client()
    response = client.post(
        "/api/segments/ghost/strategy",
        json={
            "kind": "differentiated",
            "rationale": "r",
            "expected_effect": "e",
        },
    )
    assert response.status_code == 404


def test_deleting_a_segment_leaves_outcomes_untouched() -> None:
    client, repo = _client()
    service, job, outcomes = _seed(repo, [(9.0, 3.0)])
    segment = client.post(
        "/api/segments",
        json={
            "job_id": job.id,
            "name": "Group",
            "criterion": "Any group.",
            "outcome_ids": [outcomes[0].id],
        },
    ).json()

    client.delete(f"/api/segments/{segment['id']}")

    assert client.get(f"/api/segments?job_id={job.id}").json() == []
    assert service.get_outcome(outcomes[0].id) is not None
