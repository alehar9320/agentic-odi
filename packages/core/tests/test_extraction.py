"""Tests for A4 — extracting candidate outcomes from one quote.

Every test uses the fixture extractor: no network, no model call.
"""

from __future__ import annotations

import asyncio

import pytest
from agentic_odi_core.extraction import (
    ExtractionError,
    FixtureStatementExtractor,
    Proposal,
    extract_candidates,
)
from agentic_odi_core.models import CandidateStatus
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService

VALID = "Minimize the time it takes to onboard a new customer when they sign up."
INVALID = "This is bad."


def _run(coro):
    return asyncio.run(coro)


def _repo_with_job():
    repo = InMemoryRepository()
    job = ODIService(repo).add_job("Onboard customers")
    return repo, job


def test_valid_and_invalid_proposals_are_stored_with_status() -> None:
    repo, job = _repo_with_job()
    extractor = FixtureStatementExtractor(
        [
            Proposal(statement=VALID, confidence=0.9),
            Proposal(statement="Minimize the cost of onboarding when a customer signs up."),
            Proposal(statement=INVALID),
        ]
    )
    candidates = _run(
        extract_candidates(repo, extractor, quote_id="q1", quote="ignored", job_id=job.id)
    )
    statuses = sorted(c.status.value for c in candidates)
    assert statuses == ["proposed", "proposed", "rejected"]
    rejected = next(c for c in candidates if c.status is CandidateStatus.REJECTED)
    assert rejected.rationale  # the validator's reason is kept
    assert rejected.confidence is None


def test_no_outcome_exists_after_extraction() -> None:
    repo, job = _repo_with_job()
    extractor = FixtureStatementExtractor([Proposal(statement=VALID)])
    _run(extract_candidates(repo, extractor, quote_id="q1", quote="ignored", job_id=job.id))
    assert repo.outcomes == {}
    assert repo.get_outcomes(job.id) == []


def test_rerunning_extraction_does_not_duplicate_candidates() -> None:
    repo, job = _repo_with_job()
    extractor = FixtureStatementExtractor([Proposal(statement=VALID), Proposal(statement=INVALID)])
    first = _run(extract_candidates(repo, extractor, quote_id="q1", quote="ignored", job_id=job.id))
    second = _run(
        extract_candidates(repo, extractor, quote_id="q1", quote="ignored", job_id=job.id)
    )
    assert len(first) == len(second) == 2
    assert len(repo.candidates) == 2


def test_rerunning_does_not_reset_a_human_decision() -> None:
    repo, job = _repo_with_job()
    extractor = FixtureStatementExtractor([Proposal(statement=VALID)])
    candidates = _run(
        extract_candidates(repo, extractor, quote_id="q1", quote="ignored", job_id=job.id)
    )
    candidate = candidates[0]
    repo.update_candidate(candidate.id, {"status": CandidateStatus.REJECTED.value})
    _run(extract_candidates(repo, extractor, quote_id="q1", quote="ignored", job_id=job.id))
    assert repo.get_candidate(candidate.id).status is CandidateStatus.REJECTED


def test_normalised_repeat_is_not_duplicated() -> None:
    repo, job = _repo_with_job()
    extractor = FixtureStatementExtractor(
        [
            Proposal(statement=VALID),
            Proposal(
                statement="Minimize the TIME it takes to onboard a new customer when they sign up!"
            ),
        ]
    )
    candidates = _run(
        extract_candidates(repo, extractor, quote_id="q1", quote="ignored", job_id=job.id)
    )
    assert len(candidates) == 1


def test_empty_proposal_list_stores_nothing() -> None:
    repo, job = _repo_with_job()
    extractor = FixtureStatementExtractor([])
    candidates = _run(
        extract_candidates(repo, extractor, quote_id="q1", quote="ignored", job_id=job.id)
    )
    assert candidates == []
    assert repo.candidates == {}


def test_empty_quote_is_refused() -> None:
    repo, job = _repo_with_job()
    with pytest.raises(ValueError):
        _run(
            extract_candidates(
                repo, FixtureStatementExtractor(), quote_id="q1", quote="   ", job_id=job.id
            )
        )
    assert repo.candidates == {}


def test_malformed_payload_is_refused() -> None:
    repo, job = _repo_with_job()

    class Bad:
        async def propose(self, quote, job_name=None, stage_hint=None):
            return ["not a proposal"]

    with pytest.raises(ExtractionError):
        _run(extract_candidates(repo, Bad(), quote_id="q1", quote="x", job_id=job.id))
    assert repo.candidates == {}


def test_confidence_outside_range_is_refused() -> None:
    repo, job = _repo_with_job()
    extractor = FixtureStatementExtractor([Proposal(statement=VALID, confidence=1.5)])
    with pytest.raises(ExtractionError):
        _run(extract_candidates(repo, extractor, quote_id="q1", quote="x", job_id=job.id))
    assert repo.candidates == {}


def test_empty_statement_is_refused() -> None:
    repo, job = _repo_with_job()
    extractor = FixtureStatementExtractor([Proposal(statement="  ")])
    with pytest.raises(ExtractionError):
        _run(extract_candidates(repo, extractor, quote_id="q1", quote="x", job_id=job.id))


def test_fixture_extractor_splits_sentences() -> None:
    extractor = FixtureStatementExtractor()
    proposals = _run(extractor.propose("First sentence. Second sentence!"))
    assert [p.statement for p in proposals] == ["First sentence.", "Second sentence!"]
