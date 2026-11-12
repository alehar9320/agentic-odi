"""Tests for A5 — accepting, rejecting and merging a proposed outcome."""

from __future__ import annotations

import asyncio

import pytest
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.evaluation import OutcomeStatementError
from agentic_odi_core.extraction import FixtureStatementExtractor, Proposal, extract_candidates
from agentic_odi_core.models import CandidateStatus
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.review import (
    CandidateAlreadyDecidedError,
    CandidateNotFoundError,
    accept_candidate,
    merge_candidate,
    reject_candidate,
)
from agentic_odi_core.services import JobNotFoundError, ODIService, OutcomeNotFoundError

VALID = "Minimize the time it takes to onboard a new customer when they sign up."


def _candidate(repo, job_id: str = "job"):
    extractor = FixtureStatementExtractor([Proposal(statement=VALID)])
    candidates = asyncio.run(
        extract_candidates(repo, extractor, quote_id="q1", quote="x", job_id=job_id)
    )
    return candidates[0]


def _setup():
    repo = InMemoryRepository()
    service = ODIService(repo)
    job = service.add_job("Onboard customers")
    return repo, service, job


def test_accepting_creates_exactly_one_outcome_and_links_it() -> None:
    repo, service, job = _setup()
    candidate = _candidate(repo, job.id)
    outcome = accept_candidate(service, repo, candidate.id, importance=9.0, satisfaction=4.0)
    assert len(repo.outcomes) == 1
    refreshed = repo.get_candidate(candidate.id)
    assert refreshed.status is CandidateStatus.ACCEPTED
    assert refreshed.outcome_id == outcome.id
    assert outcome.statement == VALID
    assert outcome.opportunity_score == 14.0


def test_accepting_with_edited_statement_validates_it() -> None:
    repo, service, job = _setup()
    candidate = _candidate(repo, job.id)
    with pytest.raises(OutcomeStatementError):
        accept_candidate(
            service, repo, candidate.id, statement="This is bad.", importance=5.0, satisfaction=5.0
        )
    assert repo.outcomes == {}
    assert repo.get_candidate(candidate.id).status is CandidateStatus.PROPOSED


def test_rejecting_requires_a_non_empty_reason() -> None:
    repo, service, job = _setup()
    candidate = _candidate(repo, job.id)
    with pytest.raises(ValidationError):
        reject_candidate(repo, candidate.id, reason="   ")
    assert repo.get_candidate(candidate.id).status is CandidateStatus.PROPOSED


def test_rejecting_keeps_the_candidate_and_reason() -> None:
    repo, service, job = _setup()
    candidate = _candidate(repo, job.id)
    updated = reject_candidate(repo, candidate.id, reason="duplicate")
    assert updated.status is CandidateStatus.REJECTED
    assert updated.rejection_reason == "duplicate"
    assert repo.get_candidate(candidate.id) is not None


def test_merging_creates_no_outcome_and_links_target() -> None:
    repo, service, job = _setup()
    candidate = _candidate(repo, job.id)
    target = service.add_outcome(job.id, VALID, importance=8.0, satisfaction=3.0)
    before = len(repo.outcomes)
    merged = merge_candidate(repo, candidate.id, merged_into=target.id)
    assert len(repo.outcomes) == before
    assert merged.status is CandidateStatus.MERGED
    assert merged.merged_into == target.id


def test_merging_into_unknown_outcome_is_refused() -> None:
    repo, service, job = _setup()
    candidate = _candidate(repo, job.id)
    with pytest.raises(OutcomeNotFoundError):
        merge_candidate(repo, candidate.id, merged_into="nope")
    assert repo.get_candidate(candidate.id).status is CandidateStatus.PROPOSED


def test_unknown_candidate_is_refused() -> None:
    repo, service, job = _setup()
    with pytest.raises(CandidateNotFoundError):
        reject_candidate(repo, "nope", reason="x")


def test_a_decided_candidate_cannot_be_decided_again() -> None:
    repo, service, job = _setup()
    candidate = _candidate(repo, job.id)
    accept_candidate(service, repo, candidate.id, importance=9.0, satisfaction=4.0)
    with pytest.raises(CandidateAlreadyDecidedError):
        reject_candidate(repo, candidate.id, reason="changed my mind")


def test_candidate_without_job_is_refused() -> None:
    repo = InMemoryRepository()
    service = ODIService(repo)
    extractor = FixtureStatementExtractor([Proposal(statement=VALID)])
    candidates = asyncio.run(
        extract_candidates(repo, extractor, quote_id="q1", quote="x", job_id="ghost")
    )
    with pytest.raises(JobNotFoundError):
        accept_candidate(service, repo, candidates[0].id, importance=5.0, satisfaction=5.0)


def test_router_drives_three_decisions_and_asserts_the_store() -> None:
    """Three decisions through the state machine, asserting the resulting store."""
    repo, service, job = _setup()
    extractor = FixtureStatementExtractor(
        [
            Proposal(
                statement="Minimize the time it takes to onboard a new customer when they sign up."
            ),
            Proposal(statement="Minimize the cost of onboarding a customer when they sign up."),
            Proposal(statement="Maximize the number of errors a customer hits when they sign up."),
        ]
    )
    candidates = asyncio.run(
        extract_candidates(repo, extractor, quote_id="q1", quote="x", job_id=job.id)
    )
    accepted = accept_candidate(service, repo, candidates[0].id, importance=9.0, satisfaction=4.0)
    reject_candidate(repo, candidates[1].id, reason="covered by the first")
    merge_candidate(repo, candidates[2].id, merged_into=accepted.id)

    assert len(repo.outcomes) == 1
    statuses = {c.id: c.status for c in repo.list_candidates(quote_id="q1")}
    assert statuses[candidates[0].id] is CandidateStatus.ACCEPTED
    assert statuses[candidates[1].id] is CandidateStatus.REJECTED
    assert statuses[candidates[2].id] is CandidateStatus.MERGED
    assert repo.list_candidates(status=CandidateStatus.PROPOSED) == []
