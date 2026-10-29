"""Tests for accepting or rejecting a candidate without losing evidence (A5.1a).

The state machine owns one thing: a reviewer's decision is either an outcome
with the quote still attached, or a rejection with a reason. Every test here
names the failure it pins, because the interesting cases are the boundaries —
retry, invalid edit, missing link, and an evidence write that fails.
"""

from __future__ import annotations

import pytest
from agentic_odi_core import (
    CandidateNotFoundError,
    CandidateStatus,
    InMemoryRepository,
    InvalidOutcomeStatementError,
    ODIService,
)
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.extraction import Proposal

VALID = "Minimize the time it takes to onboard when a new hire starts"
VALID_TWO = "Maximize the number of accounts created when onboarding"
INVALID = "Setup is slow"
QUOTE_TEXT = "Setup takes forever."


class ScriptedExtractor:
    """Returns a fixed list of proposals, ignoring the quote."""

    def __init__(self, proposals: list[Proposal]) -> None:
        self._proposals = proposals

    def propose(self, quote, interview, stage_hint=None):  # noqa: ANN001, ANN201
        return list(self._proposals)


class FailingEvidenceRepository(InMemoryRepository):
    """Fails every evidence write, to test the acceptance failure boundary."""

    def add_evidence(self, evidence):  # noqa: ANN001, ANN201
        raise RuntimeError("evidence store unavailable")


@pytest.fixture
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _candidate(service: ODIService, candidate_id: str):
    """Fetch a candidate the test knows exists, so mypy sees a non-optional."""
    candidate = service.get_candidate(candidate_id)
    assert candidate is not None
    return candidate


def _interview_with_quote(service: ODIService) -> tuple[str, str, str]:
    job = service.add_job("Onboard")
    interview = service.add_interview(
        title="Ana onboarding", participant_label="Ana", job_id=job.id
    )
    quote = service.add_quote(interview_id=interview.id, text=QUOTE_TEXT)
    return job.id, interview.id, quote.id


def _seed_candidates(service: ODIService, proposals: list[Proposal]) -> tuple[str, str, list]:
    """Seed a job/interview/quote and return (job_id, interview_id, candidates).

    All stored candidates come back, including any the validator refused, so a
    test can reopen a rejected one and edit it.
    """
    job_id, interview_id, quote_id = _interview_with_quote(service)
    candidates = service.extract_candidates(quote_id, ScriptedExtractor(proposals))
    return job_id, interview_id, candidates


def test_accepting_a_candidate_writes_one_outcome_one_evidence_and_one_accepted_candidate(
    service: ODIService,
) -> None:
    job_id, interview_id, candidates = _seed_candidates(service, [Proposal(VALID, 0.9)])
    candidate = candidates[0]

    accepted, outcome, evidence = service.accept_candidate(
        candidate.id, importance=8.0, satisfaction=3.0
    )

    assert accepted.status is CandidateStatus.ACCEPTED
    assert accepted.outcome_id == outcome.id
    assert outcome.statement == VALID
    # The evidence is the quote verbatim, still pointing at the outcome.
    assert evidence.outcome_id == outcome.id
    assert evidence.source_kind == "interview"
    assert evidence.source_name == "Ana onboarding"
    assert evidence.content == QUOTE_TEXT
    assert evidence.raw == {"interview_id": interview_id, "quote_id": candidate.quote_id}
    assert len(service.list_evidence(outcome_id=outcome.id)) == 1
    assert len(service.get_outcomes(job_id)) == 1


def test_accepting_twice_does_not_duplicate_the_outcome_or_the_evidence(
    service: ODIService,
) -> None:
    _, _, candidates = _seed_candidates(service, [Proposal(VALID)])
    candidate = candidates[0]

    _, first_outcome, first_evidence = service.accept_candidate(
        candidate.id, importance=8.0, satisfaction=3.0
    )
    retried, second_outcome, second_evidence = service.accept_candidate(
        candidate.id, importance=8.0, satisfaction=3.0
    )

    assert retried.outcome_id == first_outcome.id
    assert second_outcome.id == first_outcome.id
    assert second_evidence.id == first_evidence.id
    assert len(service.list_evidence(outcome_id=first_outcome.id)) == 1
    assert len(service.get_outcomes(first_outcome.job_id)) == 1


def test_accepting_with_an_edited_statement_stores_the_edit_and_the_original_quote(
    service: ODIService,
) -> None:
    _, _, candidates = _seed_candidates(service, [Proposal(INVALID)])
    candidate = candidates[0]
    # The extractor produced an invalid statement, so it is stored rejected; the
    # reviewer reopens it and edits it into a valid one before accepting.
    assert candidate.status is CandidateStatus.REJECTED
    service.update_candidate(candidate.id, {"status": CandidateStatus.PROPOSED})

    accepted, outcome, evidence = service.accept_candidate(
        candidate.id, importance=5.0, satisfaction=5.0, statement=VALID_TWO
    )

    assert accepted.statement == VALID_TWO
    assert outcome.statement == VALID_TWO
    assert evidence.content == QUOTE_TEXT


def test_an_invalid_edited_statement_is_refused_without_writing_an_outcome(
    service: ODIService,
) -> None:
    job_id, _, candidates = _seed_candidates(service, [Proposal(VALID)])
    candidate = candidates[0]

    with pytest.raises(InvalidOutcomeStatementError):
        service.accept_candidate(candidate.id, importance=8.0, satisfaction=3.0, statement=INVALID)

    assert _candidate(service, candidate.id).status is CandidateStatus.PROPOSED
    assert service.list_evidence() == []
    assert service.get_outcomes(job_id) == []


def test_a_failed_evidence_write_cannot_leave_an_orphan_outcome() -> None:
    failing = ODIService(FailingEvidenceRepository())
    job_id, _, candidates = _seed_candidates(failing, [Proposal(VALID)])
    candidate = candidates[0]

    with pytest.raises(RuntimeError):
        failing.accept_candidate(candidate.id, importance=8.0, satisfaction=3.0)

    # The new outcome was rolled back, so nothing dangles.
    assert failing.get_outcomes(job_id) == []
    assert failing.list_evidence() == []
    assert _candidate(failing, candidate.id).status is CandidateStatus.PROPOSED


def test_an_unlinked_interview_refuses_acceptance_without_writing(
    service: ODIService,
) -> None:
    interview = service.add_interview(title="No job", participant_label="Ana")
    quote = service.add_quote(interview_id=interview.id, text=QUOTE_TEXT)
    candidate = service.extract_candidates(quote.id, ScriptedExtractor([Proposal(VALID)]))[0]

    with pytest.raises(ValidationError):
        service.accept_candidate(candidate.id, importance=8.0, satisfaction=3.0)

    assert service.list_evidence() == []
    assert _candidate(service, candidate.id).status is CandidateStatus.PROPOSED


def test_rejecting_requires_a_nonblank_reason_and_changes_nothing_otherwise(
    service: ODIService,
) -> None:
    _, _, candidates = _seed_candidates(service, [Proposal(VALID)])
    candidate = candidates[0]

    with pytest.raises(ValidationError):
        service.reject_candidate(candidate.id, reason="   ")

    unchanged = _candidate(service, candidate.id)
    assert unchanged.status is CandidateStatus.PROPOSED
    assert unchanged.decision_reason is None


def test_a_valid_rejection_keeps_the_candidate_and_its_quote(service: ODIService) -> None:
    _, _, candidates = _seed_candidates(service, [Proposal(VALID)])
    candidate = candidates[0]

    rejected = service.reject_candidate(candidate.id, reason="not a real need")

    assert rejected.status is CandidateStatus.REJECTED
    assert rejected.decision_reason == "not a real need"
    assert rejected.quote_id == candidate.quote_id
    assert service.get_quote(candidate.quote_id) is not None


def test_rejecting_an_accepted_candidate_is_refused_to_avoid_an_orphan_outcome(
    service: ODIService,
) -> None:
    _, _, candidates = _seed_candidates(service, [Proposal(VALID)])
    candidate = candidates[0]
    _, outcome, _ = service.accept_candidate(candidate.id, importance=8.0, satisfaction=3.0)

    with pytest.raises(ValidationError):
        service.reject_candidate(candidate.id, reason="changed my mind")

    assert service.get_outcome(outcome.id) is not None
    assert _candidate(service, candidate.id).status is CandidateStatus.ACCEPTED


def test_accepting_an_unknown_candidate_raises_the_not_found_error(service: ODIService) -> None:
    with pytest.raises(CandidateNotFoundError):
        service.accept_candidate("missing", importance=8.0, satisfaction=3.0)


def test_rejecting_an_unknown_candidate_raises_the_not_found_error(service: ODIService) -> None:
    with pytest.raises(CandidateNotFoundError):
        service.reject_candidate("missing", reason="no such thing")


def test_acceptance_survives_sqlite_reload(tmp_path) -> None:
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    service = ODIService(repo)
    _, _, candidates = _seed_candidates(service, [Proposal(VALID)])
    candidate = candidates[0]

    _, outcome, evidence = service.accept_candidate(candidate.id, importance=8.0, satisfaction=3.0)
    repo.reload()

    reloaded = _candidate(service, candidate.id)
    assert reloaded.status is CandidateStatus.ACCEPTED
    assert reloaded.outcome_id == outcome.id
    stored = service.list_evidence(outcome_id=outcome.id)
    assert len(stored) == 1
    assert stored[0].id == evidence.id
    assert service.get_outcome(outcome.id) is not None
