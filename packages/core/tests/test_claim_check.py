"""A score carries the questions that produced it.

The claim check is the provenance behind an opportunity score: which questions
were asked, what was answered, and which questions were skipped and why. These
tests pin the model, the validation rules, and the SQLite round trip.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.models import ClaimCheck, ClaimSkip, Job, Outcome
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ClaimCheckError, ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository

_STATEMENT = "Minimize the time it takes to onboard a customer when they sign up."


def _job() -> Job:
    return Job(id="job-1", name="Onboard customers")


def _answered_check() -> ClaimCheck:
    return ClaimCheck(
        asked=["How often does this happen?", "What do you do today?"],
        answers=["Every week", "A spreadsheet"],
    )


def test_a_claim_check_round_trips_through_sqlite_unchanged(tmp_path) -> None:
    db_path = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path)
    job = repo.add_job(_job())
    outcome = repo.add_outcome(
        Outcome(
            id="outcome-1",
            job_id=job.id,
            statement=_STATEMENT,
            importance=8.0,
            satisfaction=3.0,
            opportunity_score=13.0,
            claim_check=ClaimCheck(
                asked=[
                    "How often does this happen?",
                    "What do you do today?",
                    "What does it cost?",
                ],
                answers=["Every week", "A spreadsheet"],
                skips=[ClaimSkip(question="What does it cost?", reason="never measured")],
            ),
        )
    )

    reloaded = SQLiteRepository(db_path)

    stored = reloaded.get_outcome("outcome-1")
    assert stored is not None
    assert stored.claim_check == outcome.claim_check
    assert stored.claim_check is not None
    assert stored.claim_check.skips[0].reason == "never measured"
    assert stored.claim_check.verified is True


def test_an_outcome_can_carry_a_claim_check_through_the_service() -> None:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Onboard customers")

    outcome = service.add_outcome(
        job.id,
        _STATEMENT,
        importance=8.0,
        satisfaction=3.0,
        claim_check=_answered_check(),
    )

    assert outcome.claim_check == _answered_check()
    assert service.get_outcome(outcome.id).claim_check.verified is True  # type: ignore[union-attr]


def test_a_claim_check_is_accepted_as_a_plain_dict() -> None:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Onboard customers")

    outcome = service.add_outcome(
        job.id,
        _STATEMENT,
        importance=8.0,
        satisfaction=3.0,
        claim_check={
            "asked": ["How often does this happen?"],
            "answers": ["Every week"],
        },
    )

    assert outcome.claim_check == ClaimCheck(
        asked=["How often does this happen?"], answers=["Every week"]
    )


def test_a_skip_without_a_reason_is_rejected() -> None:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Onboard customers")

    with pytest.raises(ClaimCheckError) as raised:
        service.add_outcome(
            job.id,
            _STATEMENT,
            importance=8.0,
            satisfaction=3.0,
            claim_check={
                "asked": ["What does it cost?"],
                "skips": [{"question": "What does it cost?", "reason": "   "}],
            },
        )

    assert "reason" in str(raised.value)
    assert service.get_outcomes(job.id) == []


def test_an_answer_without_a_question_is_rejected() -> None:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Onboard customers")

    with pytest.raises(ClaimCheckError):
        service.add_outcome(
            job.id,
            _STATEMENT,
            importance=8.0,
            satisfaction=3.0,
            claim_check={"asked": [], "answers": ["Every week"]},
        )

    assert service.get_outcomes(job.id) == []


def test_an_empty_claim_check_is_rejected() -> None:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Onboard customers")

    with pytest.raises(ClaimCheckError):
        service.add_outcome(
            job.id,
            _STATEMENT,
            importance=8.0,
            satisfaction=3.0,
            claim_check={"asked": [], "answers": [], "skips": []},
        )


def test_a_blank_answer_is_rejected() -> None:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Onboard customers")

    with pytest.raises(ClaimCheckError):
        service.add_outcome(
            job.id,
            _STATEMENT,
            importance=8.0,
            satisfaction=3.0,
            claim_check={"asked": ["How often?"], "answers": ["   "]},
        )


def test_an_unscored_outcome_is_legal_without_a_claim_check() -> None:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Onboard customers")

    outcome = service.add_outcome(job.id, _STATEMENT)

    assert outcome.importance is None
    assert outcome.satisfaction is None
    assert outcome.opportunity_score is None
    assert outcome.claim_check is None


def test_a_scored_outcome_may_still_omit_a_claim_check_at_the_service() -> None:
    """The service stays permissive; the MCP gate is what refuses a bare number."""
    service = ODIService(InMemoryRepository())
    job = service.add_job("Onboard customers")

    outcome = service.add_outcome(job.id, _STATEMENT, importance=8.0, satisfaction=3.0)

    assert outcome.opportunity_score == 13.0
    assert outcome.claim_check is None


def test_verified_is_derived_from_the_answers_not_supplied() -> None:
    #: A caller cannot mark a check verified without an answer behind it.
    check = ClaimCheck(asked=["How often?"], answers=[])
    assert check.verified is False

    spoofed = ClaimCheck.model_validate({"asked": ["How often?"], "answers": [], "verified": True})
    assert spoofed.verified is False


def test_a_check_of_only_skips_is_unverified() -> None:
    check = ClaimCheck(
        asked=["What does it cost?"],
        skips=[ClaimSkip(question="What does it cost?", reason="customer unavailable")],
    )

    assert check.verified is False


def test_a_malformed_claim_check_names_the_fix() -> None:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Onboard customers")

    with pytest.raises(ClaimCheckError) as raised:
        service.add_outcome(
            job.id,
            _STATEMENT,
            importance=8.0,
            satisfaction=3.0,
            claim_check={"asked": "How often?", "answers": ["Weekly"]},
        )

    assert "claim_check" in str(raised.value)
    assert service.get_outcomes(job.id) == []


def test_a_manual_score_is_recorded_as_unverified_with_a_reason() -> None:
    #: A score typed into a form is not an interview. The manual check says so
    #: rather than leaving the score indistinguishable from an interrogated one.
    from agentic_odi_core import manual_claim_check

    check = manual_claim_check()

    assert check.verified is False
    assert check.answers == []
    assert check.asked == []
    assert check.skips[0].reason
