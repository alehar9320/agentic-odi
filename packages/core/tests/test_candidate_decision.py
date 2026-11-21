"""Accepting a candidate keeps the sentence that produced it — ALH-191.

The machine proposes, a person decides; the decision must not sever the outcome
from its evidence. These tests pin the write order (outcome, then the verbatim
quote as evidence, then the candidate flip), the rollback when that evidence
write fails, and the refusal to accept a candidate whose quote is gone.
"""

from __future__ import annotations

import asyncio

import pytest
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import CandidateStatus, Job
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.review import (
    CandidateAlreadyDecidedError,
    accept_candidate,
    reject_candidate,
)
from agentic_odi_core.services import ODIService
from agentic_odi_core.spine_extraction import (
    FixtureStatementExtractor,
    Proposal,
    extract_candidates,
)

VALID = "Minimize the time it takes to onboard a new customer when they sign up."
QUOTE = "Onboarding takes forever; I want it to be faster."


def _setup() -> tuple[InMemoryRepository, ODIService, Job]:
    repo = InMemoryRepository()
    service = ODIService(repo)
    job = service.add_job("Onboard customers")
    return repo, service, job


def _candidate(repo: InMemoryRepository, job_id: str, quote: str = QUOTE):
    extractor = FixtureStatementExtractor([Proposal(statement=VALID)])
    candidates = asyncio.run(
        extract_candidates(repo, extractor, quote_id="q1", quote=quote, job_id=job_id)
    )
    return candidates[0]


def test_acceptance_keeps_the_verbatim_quote_as_evidence() -> None:
    repo, service, job = _setup()
    candidate = _candidate(repo, job.id)
    assert candidate.quote_text == QUOTE

    outcome = accept_candidate(service, repo, candidate.id, importance=9.0, satisfaction=4.0)

    evidence = repo.list_evidence(outcome_id=outcome.id)
    assert len(evidence) == 1
    assert evidence[0].content == QUOTE
    assert evidence[0].source_kind == "interview"
    assert evidence[0].raw == {"candidate_id": candidate.id, "quote_id": "q1"}
    accepted = repo.get_extracted_candidate(candidate.id)
    assert accepted is not None
    assert accepted.status is CandidateStatus.ACCEPTED
    assert accepted.outcome_id == outcome.id


def test_a_candidate_without_its_quote_is_refused() -> None:
    repo, service, job = _setup()
    candidate = _candidate(repo, job.id)
    repo.update_extracted_candidate(candidate.id, {"quote_text": None})

    with pytest.raises(ValidationError, match="verbatim quote"):
        accept_candidate(service, repo, candidate.id, importance=9.0, satisfaction=4.0)

    assert repo.outcomes == {}
    assert repo.get_extracted_candidate(candidate.id).status is CandidateStatus.PROPOSED  # type: ignore[union-attr]


def test_a_failed_evidence_write_rolls_the_outcome_back(monkeypatch: pytest.MonkeyPatch) -> None:
    repo, service, job = _setup()
    candidate = _candidate(repo, job.id)

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("evidence store offline")

    monkeypatch.setattr(service, "add_evidence", fail)

    with pytest.raises(RuntimeError, match="evidence store offline"):
        accept_candidate(service, repo, candidate.id, importance=9.0, satisfaction=4.0)

    assert repo.outcomes == {}
    assert repo.list_evidence() == []
    still_proposed = repo.get_extracted_candidate(candidate.id)
    assert still_proposed is not None
    assert still_proposed.status is CandidateStatus.PROPOSED


def test_accepting_twice_never_duplicates_the_outcome_or_its_evidence() -> None:
    repo, service, job = _setup()
    candidate = _candidate(repo, job.id)

    outcome = accept_candidate(service, repo, candidate.id, importance=9.0, satisfaction=4.0)
    with pytest.raises(CandidateAlreadyDecidedError):
        accept_candidate(service, repo, candidate.id, importance=9.0, satisfaction=4.0)

    assert list(repo.outcomes) == [outcome.id]
    assert len(repo.list_evidence(outcome_id=outcome.id)) == 1


def test_rejecting_an_accepted_candidate_keeps_the_outcome_and_its_evidence() -> None:
    repo, service, job = _setup()
    candidate = _candidate(repo, job.id)
    outcome = accept_candidate(service, repo, candidate.id, importance=9.0, satisfaction=4.0)

    with pytest.raises(CandidateAlreadyDecidedError):
        reject_candidate(repo, candidate.id, reason="changed my mind")

    assert list(repo.outcomes) == [outcome.id]
    assert len(repo.list_evidence(outcome_id=outcome.id)) == 1
