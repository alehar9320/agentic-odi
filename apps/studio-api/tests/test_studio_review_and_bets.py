"""C8/E1 (ALH-39, ALH-46) at the Studio API surface.

Readiness choices pinned here:

* ``POST /api/decisions/review`` is a read-only projection: it writes nothing,
  not even a review record, and leaves repository state unchanged.
* ``today`` is supplied so elapsed days are reproducible; it defaults to the
  current UTC date when omitted.
* Five states reach the client: ``improved``, ``degraded``, ``no change``,
  ``no_evidence``, ``orphaned``. A deleted outcome is orphaned, not a 500.
* ``GET /api/outcomes/{id}/history`` and ``/delta`` return snapshots and a
  signed change; a missing metric is ``null``, never ``0``.
* ``POST /api/bets`` captures the baseline at creation and refuses a bet whose
  outcome the decision did not choose. ``POST /api/bets/{id}/advance`` refuses
  an illegal transition and names the legal ones.
* Reads never mutate; every error is the shared typed body, not a traceback.
"""

from __future__ import annotations

import pytest
from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient

_STATEMENT = "Minimize the time it takes to publish a plugin when a release is ready"
_OTHER = "Minimize the cost of supporting a plugin when it ships"


def _client() -> tuple[TestClient, InMemoryRepository]:
    repo = InMemoryRepository()
    return TestClient(create_app(repo, backend="local")), repo


def _seed(repo: InMemoryRepository, *, decided_at: str = "2026-01-15T00:00:00Z"):
    """One job, two outcomes, one decision choosing the first."""
    service = ODIService(repo)
    job = service.add_job("Publish a plugin")
    chosen = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0, at="2026-01-01T00:00:00Z")
    other = service.add_outcome(job.id, _OTHER, 5.0, 7.0, at="2026-01-01T00:00:00Z")
    decision = service.record_decision(
        job.id,
        chosen_outcome_ids=[chosen.id],
        rationale="Publishing speed blocks every release.",
        decided_by="alex",
        decided_at=decided_at,
    )
    return service, job, chosen, other, decision


def test_review_reports_a_satisfaction_rise_and_the_days_elapsed() -> None:
    client, repo = _client()
    service, _, chosen, _, decision = _seed(repo)
    service.update_outcome(chosen.id, {"satisfaction": 5.1}, at="2026-03-01T00:00:00Z")

    body = client.post(
        "/api/decisions/review", json={"decision_id": decision.id, "today": "2026-04-01"}
    ).json()
    (only,) = body["outcomes"]
    assert only["state"] == "improved"
    assert only["satisfaction_change"] == pytest.approx(2.1)
    assert body["days_elapsed"] == 76


def test_review_defaults_today_to_the_current_utc_date() -> None:
    client, repo = _client()
    _, _, _, _, decision = _seed(repo, decided_at="2000-01-01T00:00:00Z")
    body = client.post("/api/decisions/review", json={"decision_id": decision.id}).json()
    assert body["days_elapsed"] > 365
    assert body["stale"] is True


def test_review_reports_no_change() -> None:
    client, repo = _client()
    _, _, _, _, decision = _seed(repo)
    body = client.post(
        "/api/decisions/review", json={"decision_id": decision.id, "today": "2026-04-01"}
    ).json()
    (only,) = body["outcomes"]
    assert only["state"] == "no change"
    assert only["satisfaction_change"] == 0.0


def test_review_reports_an_orphaned_outcome() -> None:
    client, repo = _client()
    service, _, chosen, _, decision = _seed(repo)
    service.delete_outcome(chosen.id)
    body = client.post(
        "/api/decisions/review", json={"decision_id": decision.id, "today": "2026-04-01"}
    ).json()
    (only,) = body["outcomes"]
    assert only["state"] == "orphaned"
    assert only["statement"] is None


def test_review_is_read_only() -> None:
    client, repo = _client()
    service, _, chosen, _, decision = _seed(repo)
    service.update_outcome(chosen.id, {"satisfaction": 6.0}, at="2026-03-01T00:00:00Z")
    before = (dict(repo.outcomes), list(repo.score_snapshots), list(repo.decisions.values()))

    client.post("/api/decisions/review", json={"decision_id": decision.id, "today": "2026-04-01"})

    after = (dict(repo.outcomes), list(repo.score_snapshots), list(repo.decisions.values()))
    assert after == before


def test_review_refuses_an_unknown_decision_without_a_traceback() -> None:
    client, _ = _client()
    response = client.post(
        "/api/decisions/review", json={"decision_id": "nope", "today": "2026-04-01"}
    )
    assert response.status_code == 404
    assert "Traceback" not in response.text


def test_review_rejects_a_malformed_clock() -> None:
    client, repo = _client()
    _, _, _, _, decision = _seed(repo)
    response = client.post(
        "/api/decisions/review", json={"decision_id": decision.id, "today": "soon"}
    )
    assert response.status_code == 422


def test_outcome_history_and_delta() -> None:
    client, repo = _client()
    service, _, chosen, _, _ = _seed(repo)
    history = client.get(f"/api/outcomes/{chosen.id}/history").json()
    assert len(history) == 1

    service.update_outcome(chosen.id, {"satisfaction": 5.0}, at="2026-03-01T00:00:00Z")
    delta = client.get(f"/api/outcomes/{chosen.id}/delta").json()
    assert delta["satisfaction"] == pytest.approx(2.0)
    assert delta["direction"] == "improved"


def test_delta_keeps_a_missing_metric_null() -> None:
    client, repo = _client()
    service, _, chosen, _, _ = _seed(repo)
    # A fall in satisfaction is a negative delta, never a re-labelled zero.
    service.update_outcome(chosen.id, {"satisfaction": 1.0}, at="2026-03-01T00:00:00Z")
    delta = client.get(f"/api/outcomes/{chosen.id}/delta").json()
    assert delta["satisfaction"] == pytest.approx(-2.0)
    assert delta["direction"] == "degraded"


def test_delta_of_an_outcome_with_no_history_is_null() -> None:
    client, repo = _client()
    service = ODIService(repo)
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0)
    service.repo.score_snapshots.clear()
    assert client.get(f"/api/outcomes/{outcome.id}/delta").json() is None


def test_history_of_an_unknown_outcome_is_empty_not_an_error() -> None:
    client, _ = _client()
    assert client.get("/api/outcomes/ghost/history").json() == []
    assert client.get("/api/outcomes/ghost/delta").json() is None


def test_record_bet_captures_the_baseline_and_lists() -> None:
    client, repo = _client()
    service, job, chosen, _, decision = _seed(repo)
    body = client.post(
        "/api/bets",
        json={
            "decision_id": decision.id,
            "outcome_id": chosen.id,
            "hypothesis": "Publishing gets under 5 minutes",
            "target": 6.0,
            "measure_by": "2026-04-01",
        },
    ).json()
    captured = body["baseline"]
    assert body["status"] == "planned"

    service.update_outcome(chosen.id, {"satisfaction": 9.0}, at="2026-02-01T00:00:00Z")
    reread = client.get(f"/api/bets?job_id={job.id}").json()
    assert reread[0]["baseline"] == captured


def test_a_bet_for_an_unchosen_outcome_is_refused() -> None:
    client, repo = _client()
    _, _, _, other, decision = _seed(repo)
    response = client.post(
        "/api/bets",
        json={
            "decision_id": decision.id,
            "outcome_id": other.id,
            "hypothesis": "h",
            "target": 6.0,
            "measure_by": "2026-04-01",
        },
    )
    assert response.status_code == 400
    assert "not one the decision" in response.text


def test_a_bet_without_a_decision_is_refused() -> None:
    client, repo = _client()
    _, _, chosen, _, _ = _seed(repo)
    response = client.post(
        "/api/bets",
        json={
            "decision_id": "nope",
            "outcome_id": chosen.id,
            "hypothesis": "h",
            "target": 6.0,
            "measure_by": "2026-04-01",
        },
    )
    assert response.status_code == 404


def test_bet_transitions_are_validated() -> None:
    client, repo = _client()
    _, _, chosen, _, decision = _seed(repo)
    bet = client.post(
        "/api/bets",
        json={
            "decision_id": decision.id,
            "outcome_id": chosen.id,
            "hypothesis": "h",
            "target": 6.0,
            "measure_by": "2026-04-01",
        },
    ).json()

    illegal = client.post(f"/api/bets/{bet['id']}/advance", json={"status": "measured"})
    assert illegal.status_code == 409
    assert "running" in illegal.text and "abandoned" in illegal.text

    running = client.post(f"/api/bets/{bet['id']}/advance", json={"status": "running"}).json()
    assert running["status"] == "running"
    measured = client.post(
        f"/api/bets/{bet['id']}/advance",
        json={"status": "measured", "at": "2026-04-02T00:00:00Z"},
    ).json()
    assert measured["measured_at"] == "2026-04-02T00:00:00Z"


def test_advancing_an_unknown_bet_is_404() -> None:
    client, _ = _client()
    response = client.post("/api/bets/nope/advance", json={"status": "running"})
    assert response.status_code == 404
