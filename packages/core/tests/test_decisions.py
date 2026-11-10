"""Pin the recorded decision (C6, ALH-37) and its supersession contract.

Readiness choices pinned here:

* ``superseded_at``/``superseded_by`` live on the *predecessor* and are set when
  a successor is recorded; both are ISO-8601 strings.
* Provenance: ``decided_by`` (attribution, not authentication) and ``decided_at``
  (supplied at write time) are required on every decision.
* History order: ``decided_at`` ascending, then id, so a reload replays the same
  order.
* Latest decision: the last entry of that ordered history.
* Validation: empty rationale, a rejection with an empty reason, a chosen or
  rejected outcome that does not belong to the job, and an unknown confidence
  all fail *without* appending an event.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import DecisionConfidence, Rejection
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import (
    DecisionNotFoundError,
    JobNotFoundError,
    ODIService,
    OutcomeNotFoundError,
)
from agentic_odi_core.sqlite_repository import SQLiteRepository
from pydantic import ValidationError as PydanticValidationError


@pytest.fixture()
def service() -> ODIService:
    return ODIService(InMemoryRepository())


@pytest.fixture()
def job_with_outcomes(service: ODIService):
    job = service.add_job("Publish a plugin")
    first = service.add_outcome(
        job.id, "Minimize the time it takes to publish a plugin when a release is ready", 9.0, 3.0
    )
    second = service.add_outcome(
        job.id, "Minimize the cost of supporting a plugin when it ships", 5.0, 7.0
    )
    return job, first, second


def test_recording_a_decision_persists_its_fields(service, job_with_outcomes):
    job, first, second = job_with_outcomes
    decision = service.record_decision(
        job.id,
        chosen_outcome_ids=[first.id],
        rejected=[Rejection(outcome_id=second.id, reason="Cheaper to support already")],
        rationale="Publishing speed blocks every release.",
        decided_by="alex",
        decided_at="2026-10-29T10:00:00Z",
        confidence=DecisionConfidence.HIGH,
    )

    stored = service.get_decision(decision.id)
    assert stored is not None
    assert stored.chosen_outcome_ids == [first.id]
    assert stored.rejected[0].reason == "Cheaper to support already"
    assert stored.decided_by == "alex"
    assert stored.confidence is DecisionConfidence.HIGH
    assert stored.superseded_at is None and stored.superseded_by is None


def test_two_decisions_yield_an_ordered_history(service, job_with_outcomes):
    job, first, second = job_with_outcomes
    older = service.record_decision(
        job.id,
        [first.id],
        rationale="First call.",
        decided_by="a",
        decided_at="2026-01-01T00:00:00Z",
    )
    newer = service.record_decision(
        job.id,
        [second.id],
        rationale="Second call.",
        decided_by="a",
        decided_at="2026-02-01T00:00:00Z",
    )

    history = service.list_decisions(job.id)
    assert [d.id for d in history] == [older.id, newer.id]
    assert service.latest_decision(job.id).id == newer.id


def test_a_superseded_decision_stays_readable(service, job_with_outcomes):
    job, first, second = job_with_outcomes
    older = service.record_decision(
        job.id,
        [first.id],
        rationale="First call.",
        decided_by="a",
        decided_at="2026-01-01T00:00:00Z",
    )
    newer = service.record_decision(
        job.id,
        [second.id],
        rationale="Second call.",
        decided_by="a",
        decided_at="2026-02-01T00:00:00Z",
        supersedes=older.id,
    )

    predecessor = service.get_decision(older.id)
    assert predecessor is not None
    assert predecessor.superseded_by == newer.id
    assert predecessor.superseded_at == "2026-02-01T00:00:00Z"
    assert predecessor.chosen_outcome_ids == [first.id]
    assert newer.superseded_by is None


def test_empty_rationale_is_refused(service, job_with_outcomes):
    job, first, _ = job_with_outcomes
    with pytest.raises(ValidationError):
        service.record_decision(
            job.id, [first.id], rationale="   ", decided_by="a", decided_at="2026-01-01T00:00:00Z"
        )
    assert service.list_decisions(job.id) == []


def test_a_rejection_without_a_reason_is_refused(service, job_with_outcomes):
    job, first, second = job_with_outcomes
    # An empty reason is refused at the model boundary.
    with pytest.raises(PydanticValidationError):
        Rejection(outcome_id=second.id, reason="")
    # A whitespace-only reason slips past the model, so the service refuses it.
    with pytest.raises(ValidationError):
        service.record_decision(
            job.id,
            [first.id],
            rejected=[Rejection(outcome_id=second.id, reason="   ")],
            rationale="ok",
            decided_by="a",
            decided_at="2026-01-01T00:00:00Z",
        )
    assert service.list_decisions(job.id) == []


def test_a_chosen_outcome_from_another_job_is_refused(service, job_with_outcomes):
    job, first, _ = job_with_outcomes
    other_job = service.add_job("Other job")
    foreign = service.add_outcome(
        other_job.id,
        "Minimize the time it takes to publish a plugin when a release is ready",
        9.0,
        3.0,
    )
    with pytest.raises(OutcomeNotFoundError):
        service.record_decision(
            job.id, [foreign.id], rationale="ok", decided_by="a", decided_at="2026-01-01T00:00:00Z"
        )


def test_unknown_job_is_not_found(service, job_with_outcomes):
    _, first, _ = job_with_outcomes
    with pytest.raises(JobNotFoundError):
        service.record_decision(
            "does-not-exist",
            [first.id],
            rationale="ok",
            decided_by="a",
            decided_at="2026-01-01T00:00:00Z",
        )


def test_invalid_confidence_is_refused(service, job_with_outcomes):
    job, first, _ = job_with_outcomes
    with pytest.raises(ValidationError):
        service.record_decision(
            job.id,
            [first.id],
            rationale="ok",
            decided_by="a",
            decided_at="2026-01-01T00:00:00Z",
            confidence="certain",  # type: ignore[arg-type]
        )


def test_superseding_a_missing_decision_is_refused(service, job_with_outcomes):
    job, first, _ = job_with_outcomes
    with pytest.raises(DecisionNotFoundError):
        service.record_decision(
            job.id,
            [first.id],
            rationale="ok",
            decided_by="a",
            decided_at="2026-01-01T00:00:00Z",
            supersedes="does-not-exist",
        )
    assert service.list_decisions(job.id) == []


def test_deleting_the_job_cascades_to_its_decisions(service, job_with_outcomes):
    job, first, _ = job_with_outcomes
    service.record_decision(
        job.id, [first.id], rationale="ok", decided_by="a", decided_at="2026-01-01T00:00:00Z"
    )
    service.delete_job(job.id)
    assert service.list_decisions(job.id) == []


def test_sqlite_replays_the_same_history(tmp_path):
    repo = SQLiteRepository(db_path=str(tmp_path / "decisions.db"))
    service = ODIService(repo)
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(
        job.id, "Minimize the time it takes to publish a plugin when a release is ready", 9.0, 3.0
    )
    first = service.record_decision(
        job.id, [outcome.id], rationale="First.", decided_by="a", decided_at="2026-01-01T00:00:00Z"
    )
    second = service.record_decision(
        job.id,
        [outcome.id],
        rationale="Second.",
        decided_by="a",
        decided_at="2026-02-01T00:00:00Z",
        supersedes=first.id,
    )

    reloaded = SQLiteRepository(db_path=str(tmp_path / "decisions.db"))
    replay = ODIService(reloaded)
    history = replay.list_decisions(job.id)
    assert [d.id for d in history] == [first.id, second.id]
    assert history[0].superseded_by == second.id
    assert history[1].rationale == "Second."
    repo.close()
    reloaded.close()
