"""Pin the decision review contract (C8/ALH-39).

Readiness choices pinned here (the increment's blockers):

* **Five states, not three.** Each chosen outcome is ``improved``, ``degraded``,
  ``no_evidence``, the literal ``no change``, or ``orphaned``.
* **Direction is satisfaction's.** Opportunity direction is not satisfaction
  direction, so a satisfaction rise of 2.1 reports ``+2.1`` and ``improved``.
* **The baseline is never after ``decided_at``.** With no snapshot at or before
  the decision there is nothing to compare against: ``no_evidence``, never
  ``no change``.
* **A missing measurement stays unknown**, never "moved".
* **An outcome deleted since the decision is ``orphaned``**, not a crash.
* **Days elapsed uses a fixed clock**: ``today`` is always supplied.
* **A review writes nothing.** The store is byte-identical after a review,
  including for a superseded decision.
"""

from __future__ import annotations

from datetime import date

import pytest
from agentic_odi_core.models import Decision, ScoreSnapshot
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.review import (
    NO_CHANGE,
    NO_EVIDENCE,
    ORPHANED,
    review_decision,
)
from agentic_odi_core.services import DecisionNotFoundError, ODIService


@pytest.fixture()
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _scored(
    service: ODIService, job_id: str, statement: str, importance: float, satisfaction: float
):
    return service.add_outcome(
        job_id,
        statement,
        importance,
        satisfaction,
        at="2026-01-01T00:00:00Z",
    )


def test_a_satisfaction_rise_of_2_1_reports_plus_2_1(service) -> None:
    job = service.add_job("Publish a plugin")
    outcome = _scored(
        service,
        job.id,
        "Minimize the time it takes to publish a plugin when a release is ready",
        9.0,
        3.0,
    )
    decision = service.record_decision(
        job.id,
        [outcome.id],
        rationale="Publishing speed blocks every release.",
        decided_by="alex",
        decided_at="2026-01-15T00:00:00Z",
    )
    service.update_outcome(outcome.id, {"satisfaction": 5.1}, at="2026-03-01T00:00:00Z")

    review = service.review_decision(decision.id, today=date(2026, 4, 1))
    (only,) = review.outcomes
    assert only.state == "improved"
    assert only.satisfaction_change == pytest.approx(2.1)


def test_no_movement_is_reported_as_no_change(service) -> None:
    job = service.add_job("Publish a plugin")
    outcome = _scored(
        service,
        job.id,
        "Minimize the time it takes to publish a plugin when a release is ready",
        9.0,
        3.0,
    )
    decision = service.record_decision(
        job.id,
        [outcome.id],
        rationale="Blocks every release.",
        decided_by="alex",
        decided_at="2026-01-15T00:00:00Z",
    )
    service.update_outcome(
        outcome.id,
        {"statement": "Minimize the time it takes to publish a plugin when a release is ready"},
        at="2026-03-01T00:00:00Z",
    )

    review = service.review_decision(decision.id, today=date(2026, 4, 1))
    (only,) = review.outcomes
    assert only.state == NO_CHANGE
    assert only.satisfaction_change == 0.0


def test_a_deleted_outcome_is_orphaned_not_a_crash(service) -> None:
    job = service.add_job("Publish a plugin")
    outcome = _scored(
        service,
        job.id,
        "Minimize the time it takes to publish a plugin when a release is ready",
        9.0,
        3.0,
    )
    decision = service.record_decision(
        job.id,
        [outcome.id],
        rationale="Blocks every release.",
        decided_by="alex",
        decided_at="2026-01-15T00:00:00Z",
    )
    service.delete_outcome(outcome.id)

    review = service.review_decision(decision.id, today=date(2026, 4, 1))
    (only,) = review.outcomes
    assert only.state == ORPHANED
    assert only.statement is None


def test_missing_measurement_is_no_evidence_never_no_change(service) -> None:
    """A chosen outcome whose only snapshot is after the decision cannot be
    compared: it is no evidence, not a standstill."""
    job = service.add_job("Publish a plugin")
    outcome = _scored(
        service,
        job.id,
        "Minimize the time it takes to publish a plugin when a release is ready",
        9.0,
        3.0,
    )
    decision = service.record_decision(
        job.id,
        [outcome.id],
        rationale="Blocks every release.",
        decided_by="alex",
        decided_at="2026-01-15T00:00:00Z",
    )
    # Drop the snapshot at the decision moment, leaving only a later one.
    repo = service.repo
    assert isinstance(repo, InMemoryRepository)
    repo.score_snapshots = [s for s in repo.score_snapshots if s.at != "2026-01-01T00:00:00Z"]

    review = service.review_decision(decision.id, today=date(2026, 4, 1))
    (only,) = review.outcomes
    assert only.state == NO_EVIDENCE


def test_the_baseline_is_never_after_decided_at(service) -> None:
    """A snapshot taken after the decision is not the "then" side of then-vs-now."""
    job = service.add_job("Publish a plugin")
    outcome = _scored(
        service,
        job.id,
        "Minimize the time it takes to publish a plugin when a release is ready",
        9.0,
        3.0,
    )
    decision = service.record_decision(
        job.id,
        [outcome.id],
        rationale="Blocks every release.",
        decided_by="alex",
        decided_at="2026-01-15T00:00:00Z",
    )
    # A big rise recorded *after* the decision, plus a smaller later rise.
    service.update_outcome(outcome.id, {"satisfaction": 9.0}, at="2026-02-01T00:00:00Z")
    service.update_outcome(outcome.id, {"satisfaction": 9.5}, at="2026-03-01T00:00:00Z")

    review = service.review_decision(decision.id, today=date(2026, 4, 1))
    (only,) = review.outcomes
    # Measured from the 3.0 recorded before the decision, not from the 9.0 after it.
    assert only.satisfaction_change == pytest.approx(6.5)


def test_days_elapsed_uses_the_supplied_clock(service) -> None:
    job = service.add_job("Publish a plugin")
    outcome = _scored(
        service,
        job.id,
        "Minimize the time it takes to publish a plugin when a release is ready",
        9.0,
        3.0,
    )
    decision = service.record_decision(
        job.id,
        [outcome.id],
        rationale="Blocks every release.",
        decided_by="alex",
        decided_at="2026-01-01T00:00:00Z",
    )
    review = service.review_decision(decision.id, today=date(2026, 1, 11))
    assert review.days_elapsed == 10
    assert review.stale is False

    stale = service.review_decision(decision.id, today=date(2026, 6, 1))
    assert stale.days_elapsed == 151
    assert stale.stale is True


def test_a_review_writes_nothing(service) -> None:
    job = service.add_job("Publish a plugin")
    outcome = _scored(
        service,
        job.id,
        "Minimize the time it takes to publish a plugin when a release is ready",
        9.0,
        3.0,
    )
    decision = service.record_decision(
        job.id,
        [outcome.id],
        rationale="Blocks every release.",
        decided_by="alex",
        decided_at="2026-01-15T00:00:00Z",
    )
    repo = service.repo
    assert isinstance(repo, InMemoryRepository)
    before = (dict(repo.outcomes), list(repo.score_snapshots), list(repo.decisions.values()))

    service.review_decision(decision.id, today=date(2026, 4, 1))

    after = (dict(repo.outcomes), list(repo.score_snapshots), list(repo.decisions.values()))
    assert after == before


def test_a_superseded_decision_reviews_the_same(service) -> None:
    job = service.add_job("Publish a plugin")
    outcome = _scored(
        service,
        job.id,
        "Minimize the time it takes to publish a plugin when a release is ready",
        9.0,
        3.0,
    )
    first = service.record_decision(
        job.id,
        [outcome.id],
        rationale="First.",
        decided_by="alex",
        decided_at="2026-01-15T00:00:00Z",
    )
    service.record_decision(
        job.id,
        [outcome.id],
        rationale="Second.",
        decided_by="alex",
        decided_at="2026-02-15T00:00:00Z",
        supersedes=first.id,
    )
    service.update_outcome(outcome.id, {"satisfaction": 4.0}, at="2026-03-01T00:00:00Z")

    review = service.review_decision(first.id, today=date(2026, 4, 1))
    (only,) = review.outcomes
    assert only.satisfaction_change == pytest.approx(1.0)


def test_unknown_decision_is_refused(service) -> None:
    with pytest.raises(DecisionNotFoundError):
        service.review_decision("nope", today=date(2026, 4, 1))


def test_review_pure_function_covers_all_five_states() -> None:
    decision = Decision(
        id="d1",
        job_id="j1",
        chosen_outcome_ids=["o1", "o2", "o3", "o4", "missing"],
        rationale="All five.",
        decided_by="alex",
        decided_at="2026-01-01T00:00:00Z",
    )

    class _Outcome:
        def __init__(self, oid: str, statement: str) -> None:
            self.id = oid
            self.statement = statement

    outcomes = [_Outcome(f"o{i}", f"Outcome {i}") for i in range(1, 5)]
    snapshots = [
        ScoreSnapshot(outcome_id="o1", at="2025-12-01T00:00:00Z", satisfaction=2.0),
        ScoreSnapshot(outcome_id="o1", at="2026-03-01T00:00:00Z", satisfaction=4.0),
        ScoreSnapshot(outcome_id="o2", at="2025-12-01T00:00:00Z", satisfaction=5.0),
        ScoreSnapshot(outcome_id="o2", at="2026-03-01T00:00:00Z", satisfaction=3.0),
        ScoreSnapshot(outcome_id="o3", at="2025-12-01T00:00:00Z", satisfaction=4.0),
        ScoreSnapshot(outcome_id="o3", at="2026-03-01T00:00:00Z", satisfaction=4.0),
        # o4 has no snapshot at or before the decision.
        ScoreSnapshot(outcome_id="o4", at="2026-02-01T00:00:00Z", satisfaction=6.0),
    ]

    review = review_decision(decision, outcomes, snapshots, today=date(2026, 4, 1))
    states = [o.state for o in review.outcomes]
    assert states == ["improved", "degraded", NO_CHANGE, NO_EVIDENCE, ORPHANED]
