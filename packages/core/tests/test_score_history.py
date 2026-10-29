"""A score keeps its history, so "did it move?" is a subtraction.

Every accepted score mutation writes one snapshot that carries the score *and*
its sample/method companions. The tests here pin that contract: a snapshot per
accepted change, none for a rejected one, companions preserved, and the same
behaviour from both repositories after a reload.

Signed deltas are deliberately absent: the baseline/sign policy is a pending
decision, so only the recorded states are asserted.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentic_odi_core.models import Outcome, ScoreSnapshot
from agentic_odi_core.repository import InMemoryRepository, Repository
from agentic_odi_core.services import (
    ODIService,
    OutcomeNotFoundError,
    SnapshotNoteError,
    ValueOutOfRangeError,
)
from agentic_odi_core.sqlite_repository import SQLiteRepository
from pydantic import ValidationError

_STATEMENT = "Minimize the time it takes to onboard a new engineer when they join."


@pytest.fixture(params=["memory", "sqlite"])
def repo(request: pytest.FixtureRequest, tmp_path: Path) -> Repository:
    if request.param == "memory":
        return InMemoryRepository()
    return SQLiteRepository(str(tmp_path / "odi.db"))


def _service(repo: Repository) -> ODIService:
    service = ODIService(repo)
    service.add_job("Onboard")
    return service


def _first_job_id(service: ODIService) -> str:
    return service.get_jobs()[0].id


def _add(service: ODIService, **overrides: object) -> Outcome:
    base: dict[str, object] = {
        "job_id": _first_job_id(service),
        "statement": _STATEMENT,
        "importance": 8.0,
        "satisfaction": 6.0,
    }
    base.update(overrides)
    return service.add_outcome(**base)  # type: ignore[arg-type]


def _reopen(repo: Repository) -> ODIService:
    if isinstance(repo, SQLiteRepository):
        repo.reload()
    return ODIService(repo)


def test_creating_an_outcome_records_its_first_snapshot(repo: Repository) -> None:
    service = _service(repo)
    outcome = _add(service, importance_n=40, satisfaction_n=40, score_method="survey")

    history = _reopen(repo).get_score_history(outcome.id)

    assert len(history) == 1
    only = history[0]
    assert (only.importance, only.satisfaction) == (8.0, 6.0)
    assert (only.importance_n, only.satisfaction_n, only.method) == (40, 40, "survey")
    assert only.opportunity_score == outcome.opportunity_score


def test_an_update_records_a_second_snapshot_not_a_rewrite(repo: Repository) -> None:
    service = _service(repo)
    outcome = _add(service)
    service.update_outcome(outcome.id, {"satisfaction": 4.0})

    history = _reopen(repo).get_score_history(outcome.id)

    assert [(s.importance, s.satisfaction) for s in history] == [(8.0, 6.0), (8.0, 4.0)]


def test_a_snapshot_carries_the_note_that_was_given(repo: Repository) -> None:
    service = _service(repo)
    outcome = _add(service, note="from the Q3 survey")
    service.update_outcome(outcome.id, {"importance": 9.0}, note="after the redesign")

    history = _reopen(repo).get_score_history(outcome.id)

    assert [s.note for s in history] == ["from the Q3 survey", "after the redesign"]


def test_an_omitted_note_stays_unknown_not_empty(repo: Repository) -> None:
    service = _service(repo)
    outcome = _add(service)

    assert _reopen(repo).get_score_history(outcome.id)[0].note is None


def test_a_rejected_mutation_leaves_no_snapshot(repo: Repository) -> None:
    service = _service(repo)
    outcome = _add(service)

    with pytest.raises(ValueOutOfRangeError):
        service.update_outcome(outcome.id, {"score_method": "estimate", "importance_n": 40})

    history = _reopen(repo).get_score_history(outcome.id)
    assert len(history) == 1


def test_an_over_long_note_is_refused_before_any_snapshot(repo: Repository) -> None:
    service = _service(repo)
    outcome = _add(service)

    with pytest.raises(SnapshotNoteError):
        service.update_outcome(outcome.id, {"importance": 9.0}, note="x" * 501)

    history = _reopen(repo).get_score_history(outcome.id)
    assert len(history) == 1
    assert history[0].importance == 8.0


def test_history_of_an_unknown_outcome_is_refused(repo: Repository) -> None:
    service = _service(repo)
    with pytest.raises(OutcomeNotFoundError):
        service.get_score_history("no-such-outcome")


def test_deleting_an_outcome_drops_its_history(repo: Repository) -> None:
    service = _service(repo)
    outcome = _add(service)
    service.update_outcome(outcome.id, {"satisfaction": 4.0})
    service.delete_outcome(outcome.id)

    assert repo.list_score_snapshots(outcome.id) == []


def test_unknown_scores_are_recorded_as_unknown(repo: Repository) -> None:
    service = _service(repo)
    outcome = _add(service)

    only = _reopen(repo).get_score_history(outcome.id)[0]
    assert only.importance_n is None
    assert only.satisfaction_n is None
    assert only.method == "estimate"


def test_a_snapshot_with_a_zero_count_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ScoreSnapshot(outcome_id="outcome-1", importance_n=0)


def test_a_snapshot_timestamp_is_iso_utc() -> None:
    snapshot = ScoreSnapshot(outcome_id="outcome-1")
    assert snapshot.at.endswith("+00:00")
