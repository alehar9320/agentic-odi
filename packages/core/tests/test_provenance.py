"""Provenance travels with the number (A10 / ALH-23).

Acceptance writes one verbatim ``Evidence`` row per quote; deleting the
interview keeps that evidence readable and nulls only the quote pointer, so a
decision made from a quote survives the transcript being deleted. The count a
surface shows is ``list_evidence``, never a stored counter.
"""

from __future__ import annotations

import pytest
from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_core.extraction import FixtureExtractor, Proposal

QUOTE_TEXT = "Setup takes forever when a new hire starts."


@pytest.fixture
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _accepted(service: ODIService) -> tuple[str, str, str]:
    """Return (job_id, interview_id, outcome_id) with one accepted candidate."""
    job = service.add_job("Onboard")
    interview = service.add_interview(
        title="Ana onboarding", participant_label="Ana", job_id=job.id
    )
    quote = service.add_quote(interview_id=interview.id, text=QUOTE_TEXT)
    candidate = service.extract_candidates(
        quote.id,
        FixtureExtractor(
            {QUOTE_TEXT: [Proposal("Minimize the time it takes to onboard when a new hire starts")]}
        ),
    )[0]
    _, outcome, _ = service.accept_candidate(candidate.id, importance=8.0, satisfaction=3.0)
    return job.id, interview.id, outcome.id


def test_an_accepted_outcome_has_evidence_equal_to_the_quote_verbatim(
    service: ODIService,
) -> None:
    _, _, outcome_id = _accepted(service)

    evidence = service.list_evidence(outcome_id=outcome_id)

    assert len(evidence) == 1
    assert evidence[0].content == QUOTE_TEXT
    assert evidence[0].source_kind == "interview"
    assert evidence[0].source_name == "Ana onboarding"


def test_deleting_the_interview_keeps_the_evidence_readable_and_nulls_only_the_quote_link(
    service: ODIService,
) -> None:
    # The reason is in the name: a decision made from a quote must outlive the
    # transcript, and a dangling link is the honest representation of that.
    _, interview_id, outcome_id = _accepted(service)

    service.delete_interview(interview_id)

    evidence = service.list_evidence(outcome_id=outcome_id)
    assert len(evidence) == 1, "the evidence must survive the interview"
    assert evidence[0].content == QUOTE_TEXT, "the verbatim quote stays readable"
    assert evidence[0].source_name == "Ana onboarding", "the interview title stays readable"
    assert evidence[0].raw["quote_id"] is None, "the quote pointer is nulled"
    assert evidence[0].raw["interview_id"] == interview_id, "the historical id is kept"


def test_deleting_the_interview_leaves_unrelated_evidence_untouched(
    service: ODIService,
) -> None:
    _, interview_id, _ = _accepted(service)
    other = service.add_evidence(
        source_name="Support ticket",
        source_kind="manual",
        name="note",
        content="Something else entirely.",
    )

    service.delete_interview(interview_id)

    stored = service.get_evidence(other.id)
    assert stored is not None
    assert stored.raw == {}


def test_the_evidence_count_is_list_evidence_not_a_stored_counter(
    service: ODIService,
) -> None:
    _, _, outcome_id = _accepted(service)
    before = len(service.list_evidence(outcome_id=outcome_id))

    # Deleting one evidence row must move the count, which a denormalised
    # counter would not.
    service.delete_evidence(service.list_evidence(outcome_id=outcome_id)[0].id)

    assert len(service.list_evidence(outcome_id=outcome_id)) == before - 1


def test_the_nulled_quote_link_survives_sqlite_replay(tmp_path) -> None:
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    db = str(tmp_path / "odi.db")
    service = ODIService(SQLiteRepository(db))
    _, interview_id, outcome_id = _accepted(service)
    service.delete_interview(interview_id)

    live = service.list_evidence(outcome_id=outcome_id)
    assert live[0].raw["quote_id"] is None

    service.repo.reload()
    after_replay = service.list_evidence(outcome_id=outcome_id)
    assert after_replay == live, "replay must reproduce the nulled link, not the original"


def test_repeated_acceptance_keeps_one_evidence_link_per_source(
    service: ODIService,
) -> None:
    job = service.add_job("Onboard")
    interview = service.add_interview(
        title="Ana onboarding", participant_label="Ana", job_id=job.id
    )
    quote = service.add_quote(interview_id=interview.id, text=QUOTE_TEXT)
    candidate = service.extract_candidates(
        quote.id,
        FixtureExtractor(
            {QUOTE_TEXT: [Proposal("Minimize the time it takes to onboard when a new hire starts")]}
        ),
    )[0]

    _, outcome, first = service.accept_candidate(candidate.id, importance=8.0, satisfaction=3.0)
    _, same_outcome, retry = service.accept_candidate(
        candidate.id, importance=8.0, satisfaction=3.0
    )

    assert same_outcome.id == outcome.id
    assert retry.id == first.id, "a retry must not write a second evidence row"
    assert len(service.list_evidence(outcome_id=outcome.id)) == 1


def test_the_evidence_snapshot_does_not_invent_a_speaker_or_date(
    service: ODIService,
) -> None:
    # Once the interview is gone there is no speaker or date to show. The
    # snapshot must not fabricate attribution from the deleted record.
    _, interview_id, outcome_id = _accepted(service)
    service.delete_interview(interview_id)

    evidence = service.list_evidence(outcome_id=outcome_id)[0]

    assert "speaker" not in evidence.raw
    assert "conducted_at" not in evidence.raw
    assert evidence.raw["interview_id"] == interview_id
