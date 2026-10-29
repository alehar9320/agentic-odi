"""Router tests for provenance (A10 / ALH-23).

``GET /api/outcomes/{id}/evidence`` reads ``list_evidence``; the count a surface
shows is that list's length. An unknown outcome is a not-found error, distinct
from an outcome that simply has no evidence yet. Deleting the interview keeps
the evidence readable and nulls the quote link.
"""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_core.extraction import FixtureExtractor, Proposal
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient

VALID = "Minimize the time it takes to onboard when a new hire starts"
QUOTE_TEXT = "Setup takes forever."


def _client_with_accepted_outcome() -> tuple[TestClient, ODIService, str, str]:
    """Return (client, service, interview_id, outcome_id)."""
    repo = InMemoryRepository()
    service = ODIService(repo)
    client = TestClient(create_app(repo, backend="local"))
    job = service.add_job("Onboard")
    interview = service.add_interview(
        title="Ana onboarding", participant_label="Ana", job_id=job.id
    )
    quote = service.add_quote(interview_id=interview.id, text=QUOTE_TEXT)
    extractor = FixtureExtractor({QUOTE_TEXT: [Proposal(VALID)]})
    candidate = service.extract_candidates(quote.id, extractor)[0]
    _, outcome, _ = service.accept_candidate(candidate.id, importance=8.0, satisfaction=3.0)
    return client, service, interview.id, outcome.id


def test_get_outcome_evidence_returns_the_verbatim_quote() -> None:
    client, _, _, outcome_id = _client_with_accepted_outcome()

    response = client.get(f"/api/outcomes/{outcome_id}/evidence")

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["result"]) == 1
    assert body["result"][0]["content"] == QUOTE_TEXT
    assert body["result"][0]["source_kind"] == "interview"


def test_get_outcome_evidence_is_empty_for_an_outcome_with_no_evidence() -> None:
    client, service, _, _ = _client_with_accepted_outcome()
    job = service.add_job("Empty")
    outcome = service.add_outcome(job.id, VALID, importance=5.0, satisfaction=5.0)

    response = client.get(f"/api/outcomes/{outcome.id}/evidence")

    assert response.status_code == 200
    assert response.json()["result"] == []


def test_get_outcome_evidence_for_an_unknown_outcome_is_not_found() -> None:
    client, _, _, _ = _client_with_accepted_outcome()

    response = client.get("/api/outcomes/missing/evidence")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_the_evidence_count_matches_list_evidence_after_the_interview_is_deleted() -> None:
    client, service, interview_id, outcome_id = _client_with_accepted_outcome()

    service.delete_interview(interview_id)

    body = client.get(f"/api/outcomes/{outcome_id}/evidence").json()
    listed = service.list_evidence(outcome_id=outcome_id)
    assert len(body["result"]) == len(listed) == 1
    assert body["result"][0]["content"] == QUOTE_TEXT
    assert body["result"][0]["raw"]["quote_id"] is None


def test_the_api_and_list_evidence_agree_on_the_count_for_the_same_fixture() -> None:
    client, service, _, outcome_id = _client_with_accepted_outcome()

    body = client.get(f"/api/outcomes/{outcome_id}/evidence").json()

    assert len(body["result"]) == len(service.list_evidence(outcome_id=outcome_id))
