"""Tests for extracting outcome candidates from a quote (A4)."""

from __future__ import annotations

import pytest
from agentic_odi_core import (
    CandidateStatus,
    InMemoryRepository,
    InterviewNotFoundError,
    ODIService,
    QuoteNotFoundError,
)
from agentic_odi_core.extraction import FixtureExtractor, Proposal

VALID = "Minimize the time it takes to onboard when a new hire starts"
VALID_TWO = "Maximize the number of accounts created when onboarding"
INVALID = "Setup is slow"


class ScriptedExtractor:
    """Returns a fixed list of proposals, ignoring the quote."""

    def __init__(self, proposals: list[Proposal]) -> None:
        self._proposals = proposals

    def propose(self, quote, interview, stage_hint=None):  # noqa: ANN001, ANN201
        return list(self._proposals)


@pytest.fixture
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _interview_with_quote(
    service: ODIService, text: str = "Setup takes forever."
) -> tuple[str, str]:
    job = service.add_job("Onboard")
    interview = service.add_interview(title="T", participant_label="Ana", job_id=job.id)
    quote = service.add_quote(interview_id=interview.id, text=text)
    return interview.id, quote.id


def test_extract_stores_proposed_and_rejected(service: ODIService) -> None:
    _, quote_id = _interview_with_quote(service)
    extractor = ScriptedExtractor(
        [
            Proposal(VALID, confidence=0.9, rationale="clear need"),
            Proposal(VALID_TWO, confidence=0.7),
            Proposal(INVALID, confidence=0.2),
        ]
    )

    candidates = service.extract_candidates(quote_id, extractor)

    assert [c.status for c in candidates] == [
        CandidateStatus.PROPOSED,
        CandidateStatus.PROPOSED,
        CandidateStatus.REJECTED,
    ]
    assert candidates[0].rationale == "clear need"
    # The rejected candidate keeps the validator's message as its rationale.
    assert candidates[2].rationale
    assert "Minimize" in candidates[2].rationale or "Maximize" in candidates[2].rationale


def test_extract_creates_no_outcome(service: ODIService) -> None:
    interview_id, quote_id = _interview_with_quote(service)
    interview = service.get_interview(interview_id)
    assert interview is not None and interview.job_id is not None
    job_id = interview.job_id
    service.extract_candidates(quote_id, ScriptedExtractor([Proposal(VALID)]))
    assert service.get_outcomes(job_id) == []


def test_extract_is_idempotent_and_does_not_reset_decisions(service: ODIService) -> None:
    _, quote_id = _interview_with_quote(service)
    extractor = ScriptedExtractor([Proposal(VALID), Proposal(VALID_TWO)])

    first = service.extract_candidates(quote_id, extractor)
    service.update_candidate(first[0].id, {"status": CandidateStatus.ACCEPTED})

    second = service.extract_candidates(quote_id, extractor)

    assert second == []
    assert len(service.list_candidates()) == 2
    accepted = service.get_candidate(first[0].id)
    assert accepted is not None
    assert accepted.status == CandidateStatus.ACCEPTED


def test_extract_collapses_normalised_duplicates(service: ODIService) -> None:
    _, quote_id = _interview_with_quote(service)
    extractor = ScriptedExtractor(
        [
            Proposal("Minimize the time it takes to onboard when a new hire starts"),
            Proposal("minimize time it takes onboard when new hire starts"),
        ]
    )
    candidates = service.extract_candidates(quote_id, extractor)
    assert len(candidates) == 1


def test_extract_unknown_quote_raises(service: ODIService) -> None:
    with pytest.raises(QuoteNotFoundError):
        service.extract_candidates("missing", ScriptedExtractor([Proposal(VALID)]))


def test_extract_unknown_interview_raises(service: ODIService) -> None:
    from agentic_odi_core.models import InterviewQuote

    # A quote whose interview is gone: the service reports the missing interview.
    service.repo.add_quote(InterviewQuote(interview_id="ghost", text="hello", ordinal=0))
    quote_id = service.list_quotes("ghost")[0].id
    with pytest.raises(InterviewNotFoundError):
        service.extract_candidates(quote_id, ScriptedExtractor([Proposal(VALID)]))


def test_extract_out_of_range_confidence_is_rejected_by_model(service: ODIService) -> None:
    _, quote_id = _interview_with_quote(service)
    with pytest.raises(ValueError):
        service.extract_candidates(quote_id, ScriptedExtractor([Proposal(VALID, confidence=1.5)]))


def test_fixture_extractor_produces_candidates_from_a_quote(service: ODIService) -> None:
    _, quote_id = _interview_with_quote(service, "Setup is slow. Docs are missing.")
    candidates = service.extract_candidates(quote_id, FixtureExtractor())
    assert candidates
    assert all(c.quote_id == quote_id for c in candidates)


def test_fixture_extractor_keeps_an_existing_direction() -> None:
    from agentic_odi_core.extraction import FixtureExtractor
    from agentic_odi_core.models import Interview, InterviewQuote

    extractor = FixtureExtractor()
    quote = InterviewQuote(interview_id="i", text="Minimize the time to onboard.", ordinal=0)
    interview = Interview(title="T", participant_label="Ana")
    proposals = extractor.propose(quote, interview)
    assert proposals[0].statement.startswith("Minimize")


def test_list_candidates_filters_by_status_and_interview(service: ODIService) -> None:
    interview_id, quote_id = _interview_with_quote(service)
    service.extract_candidates(quote_id, ScriptedExtractor([Proposal(VALID), Proposal(INVALID)]))
    assert len(service.list_candidates(interview_id=interview_id)) == 2
    assert len(service.list_candidates(status=CandidateStatus.PROPOSED)) == 1
    assert len(service.list_candidates(status=CandidateStatus.REJECTED)) == 1
    assert service.list_candidates(interview_id="other") == []


def test_update_and_delete_candidate(service: ODIService) -> None:
    _, quote_id = _interview_with_quote(service)
    candidate = service.extract_candidates(quote_id, ScriptedExtractor([Proposal(VALID)]))[0]

    updated = service.update_candidate(candidate.id, {"decision_reason": "not now"})
    assert updated.decision_reason == "not now"

    service.delete_candidate(candidate.id)
    assert service.get_candidate(candidate.id) is None


def test_deleting_an_interview_cascades_candidates(service: ODIService) -> None:
    interview_id, quote_id = _interview_with_quote(service)
    service.extract_candidates(quote_id, ScriptedExtractor([Proposal(VALID)]))
    service.delete_interview(interview_id)
    assert service.list_candidates() == []


def test_extract_empty_proposal_list_writes_nothing(service: ODIService) -> None:
    interview_id, quote_id = _interview_with_quote(service)
    created = service.extract_candidates(quote_id, ScriptedExtractor([]))
    assert created == []
    assert service.list_candidates() == []
    # No outcome is ever created by extraction, empty or not.
    interview = service.get_interview(interview_id)
    assert interview is not None and interview.job_id is not None
    assert service.get_outcomes(interview.job_id) == []


def test_extract_rejects_a_malformed_payload_without_a_partial_write(service: ODIService) -> None:
    class BrokenExtractor:
        def propose(self, quote, interview, stage_hint=None):  # noqa: ANN001, ANN201
            # The first proposal is valid; the second is malformed. Nothing may
            # be written: a bad payload cannot leave a partly-extracted quote.
            return [Proposal(VALID), object()]

    _, quote_id = _interview_with_quote(service)
    with pytest.raises(ValueError):
        service.extract_candidates(quote_id, BrokenExtractor())
    assert service.list_candidates() == []


def test_extract_rejects_an_out_of_range_confidence_without_a_partial_write(
    service: ODIService,
) -> None:
    _, quote_id = _interview_with_quote(service)
    extractor = ScriptedExtractor([Proposal(VALID), Proposal(VALID_TWO, confidence=1.5)])
    with pytest.raises(ValueError):
        service.extract_candidates(quote_id, extractor)
    # The valid proposal before the bad one is not written either.
    assert service.list_candidates() == []


def test_extract_propagates_an_extractor_failure_with_no_write(service: ODIService) -> None:
    class ExplodingExtractor:
        def propose(self, quote, interview, stage_hint=None):  # noqa: ANN001, ANN201
            raise RuntimeError("the model provider is unreachable")

    _, quote_id = _interview_with_quote(service)
    with pytest.raises(RuntimeError):
        service.extract_candidates(quote_id, ExplodingExtractor())
    assert service.list_candidates() == []
