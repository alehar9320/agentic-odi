"""Router tests for candidate review decisions (A5.1a).

The router owns the reviewer's decision: accept writes exactly one outcome with
the quote as evidence, reject keeps the candidate and its reason, and an
unknown candidate is a not-found error rather than a 500.
"""

from __future__ import annotations

from agentic_odi_core import CandidateStatus, InMemoryRepository, ODIService
from agentic_odi_core.extraction import Proposal
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient

VALID = "Minimize the time it takes to onboard when a new hire starts"
INVALID = "Setup is slow"
QUOTE_TEXT = "Setup takes forever."


class ScriptedExtractor:
    def __init__(self, proposals: list[Proposal]) -> None:
        self._proposals = proposals

    def propose(self, quote, interview, stage_hint=None):  # noqa: ANN001, ANN201
        return list(self._proposals)


def _client_with_candidate(
    proposals: list[Proposal],
) -> tuple[TestClient, ODIService, str, str]:
    """Return (client, service, job_id, candidate_id) with one stored candidate."""
    repo = InMemoryRepository()
    service = ODIService(repo)
    client = TestClient(create_app(repo, backend="local"))
    job = service.add_job("Onboard")
    interview = service.add_interview(
        title="Ana onboarding", participant_label="Ana", job_id=job.id
    )
    quote = service.add_quote(interview_id=interview.id, text=QUOTE_TEXT)
    candidate = service.extract_candidates(quote.id, ScriptedExtractor(proposals))[0]
    return client, service, job.id, candidate.id


def test_get_candidates_filters_by_interview_and_status() -> None:
    client, service, _, candidate_id = _client_with_candidate([Proposal(VALID), Proposal(INVALID)])
    stored = service.get_candidate(candidate_id)
    assert stored is not None
    interview_id = stored.interview_id

    proposed = client.get("/api/candidates", params={"status": "proposed"}).json()
    rejected = client.get("/api/candidates", params={"status": "rejected"}).json()
    by_interview = client.get("/api/candidates", params={"interview_id": interview_id}).json()
    empty = client.get("/api/candidates", params={"interview_id": "other"}).json()

    assert [c["id"] for c in proposed["result"]] == [candidate_id]
    assert all(c["status"] == "rejected" for c in rejected["result"])
    assert len(by_interview["result"]) == 2
    assert empty["result"] == []


def test_get_candidates_rejects_an_unknown_status() -> None:
    client, _, _, _ = _client_with_candidate([Proposal(VALID)])

    response = client.get("/api/candidates", params={"status": "sideways"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation"


def test_patch_accepts_a_candidate_into_one_outcome_with_evidence() -> None:
    client, service, job_id, candidate_id = _client_with_candidate([Proposal(VALID)])

    response = client.patch(
        f"/api/candidates/{candidate_id}",
        json={"status": "accepted", "importance": 8.0, "satisfaction": 3.0},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result"]["status"] == "accepted"
    assert body["result"]["outcome_id"] == body["outcome"]["id"]
    assert body["evidence"]["content"] == QUOTE_TEXT
    assert body["evidence"]["outcome_id"] == body["outcome"]["id"]

    stored = service.list_evidence(outcome_id=body["outcome"]["id"])
    assert len(stored) == 1
    assert len(service.get_outcomes(job_id)) == 1


def test_patch_accept_twice_does_not_duplicate() -> None:
    client, service, job_id, candidate_id = _client_with_candidate([Proposal(VALID)])
    body = {"status": "accepted", "importance": 8.0, "satisfaction": 3.0}

    first = client.patch(f"/api/candidates/{candidate_id}", json=body).json()
    second = client.patch(f"/api/candidates/{candidate_id}", json=body).json()

    assert first["outcome"]["id"] == second["outcome"]["id"]
    assert first["evidence"]["id"] == second["evidence"]["id"]
    assert len(service.get_outcomes(job_id)) == 1


def test_patch_accept_without_scores_is_refused() -> None:
    client, service, _, candidate_id = _client_with_candidate([Proposal(VALID)])

    response = client.patch(f"/api/candidates/{candidate_id}", json={"status": "accepted"})

    assert response.status_code == 422
    unchanged = service.get_candidate(candidate_id)
    assert unchanged is not None
    assert unchanged.status is CandidateStatus.PROPOSED


def test_patch_rejects_with_a_blank_reason() -> None:
    client, service, _, candidate_id = _client_with_candidate([Proposal(VALID)])

    response = client.patch(
        f"/api/candidates/{candidate_id}", json={"status": "rejected", "reason": "  "}
    )

    assert response.status_code == 422
    unchanged = service.get_candidate(candidate_id)
    assert unchanged is not None
    assert unchanged.status is CandidateStatus.PROPOSED


def test_patch_rejects_keeping_the_reason() -> None:
    client, service, _, candidate_id = _client_with_candidate([Proposal(VALID)])

    response = client.patch(
        f"/api/candidates/{candidate_id}",
        json={"status": "rejected", "reason": "not a real need"},
    )

    assert response.status_code == 200
    assert response.json()["result"]["decision_reason"] == "not a real need"


def test_patch_can_edit_a_statement_without_a_decision() -> None:
    client, service, _, candidate_id = _client_with_candidate([Proposal(INVALID)])

    response = client.patch(f"/api/candidates/{candidate_id}", json={"statement": "Setup is slow"})

    assert response.status_code == 200
    assert response.json()["result"]["statement"] == "Setup is slow"


def test_patch_an_unknown_candidate_is_a_not_found_error() -> None:
    client, _, _, _ = _client_with_candidate([Proposal(VALID)])

    response = client.patch(
        "/api/candidates/missing",
        json={"status": "accepted", "importance": 8.0, "satisfaction": 3.0},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
