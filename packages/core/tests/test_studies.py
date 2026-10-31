"""Tests for M2-05.2: opening a new wave and comparing two waves.

The two dangerous mistakes live here: copying the last wave's scores into the
new one, and rendering a missing score as a zero. Every test below exists to
make one of those fail loudly.
"""

from __future__ import annotations

import pytest
from agentic_odi_core import (
    InMemoryRepository,
    ODIService,
    Outcome,
    OutcomeComparisonStatus,
    StudyNotFoundError,
    StudyStatus,
)
from agentic_odi_core.services import StudyJobMismatchError
from agentic_odi_core.sqlite_repository import SQLiteRepository

_STATEMENT = "Minimize the time it takes to harvest the field when the weather turns"
_ADDED = "Minimize the cost of the fuel burned while the tractor is idling"


def _service(repo=None) -> ODIService:
    return ODIService(repo if repo is not None else InMemoryRepository())


def _opened_study(service: ODIService, job_id: str):
    return service.open_study(
        job_id=job_id,
        name="Corn growers, quarterly pulse",
        guide={"name": "Core interview", "version": "1", "questions": ["Walk me through harvest"]},
        outcome_statements=[_STATEMENT],
        themes=["yield"],
    )


def test_next_wave_copies_the_frame_by_value_and_leaves_it_unmeasured() -> None:
    service = _service()
    job = service.add_job("Corn growers", "Grow corn profitably")
    source = _opened_study(service, job.id)
    # Score wave 1 first: the dangerous mistake is copying *these* scores into
    # wave 2, and a wave with nothing measured cannot catch it.
    service.add_outcome(job.id, _STATEMENT, 8.0, 4.0, study_id=source.id)

    wave = service.next_wave(source.id)

    assert wave.wave == source.wave + 1
    assert wave.lineage_id == source.lineage_id
    assert wave.job_id == source.job_id
    assert wave.name == source.name
    assert wave.status == StudyStatus.OPEN
    # Frame matches per field...
    assert wave.frame.guide == source.frame.guide
    assert wave.frame.outcome_statements == source.frame.outcome_statements
    assert wave.frame.themes == source.frame.themes
    # ...and no measurement was carried over.
    assert [o for o in service.repo.outcomes.values() if o.study_id == wave.id] == []
    assert [o.study_id for o in service.repo.outcomes.values()] == [source.id]


def test_editing_the_copied_frame_does_not_mutate_the_source() -> None:
    service = _service()
    job = service.add_job("Corn growers", "Grow corn profitably")
    source = _opened_study(service, job.id)
    wave = service.next_wave(source.id)

    wave.frame.outcome_statements.append("Maximize the yield of the field after the rain")
    wave.frame.themes.append("cost")

    assert source.frame.outcome_statements == [_STATEMENT]
    assert source.frame.themes == ["yield"]


def test_next_wave_allocates_a_unique_wave_number_and_replays_it() -> None:
    repo = SQLiteRepository(db_path=":memory:")
    service = _service(repo)
    job = service.add_job("Corn growers", "Grow corn profitably")
    source = _opened_study(service, job.id)
    second = service.next_wave(source.id)
    third = service.next_wave(second.id)

    assert {source.wave, second.wave, third.wave} == {1, 2, 3}
    repo.reload()
    waves = service.list_studies(job_id=job.id)
    assert [w.wave for w in waves] == [1, 2, 3]
    assert [w.frame.outcome_statements for w in waves] == [[_STATEMENT]] * 3


def test_next_wave_refuses_an_unknown_study() -> None:
    service = _service()

    with pytest.raises(StudyNotFoundError):
        service.next_wave("missing")


def test_open_study_refuses_an_unknown_job() -> None:
    from agentic_odi_core import JobNotFoundError

    service = _service()

    with pytest.raises(JobNotFoundError):
        _opened_study(service, "missing")


def test_compare_reports_moved_added_and_dropped_per_statement() -> None:
    service = _service()
    job = service.add_job("Corn growers", "Grow corn profitably")
    wave_a = _opened_study(service, job.id)
    wave_b = service.next_wave(wave_a.id)
    service.add_outcome(job.id, _STATEMENT, 4.0, 4.0, study_id=wave_a.id)
    service.add_outcome(job.id, _STATEMENT, 7.0, 4.0, study_id=wave_b.id)
    service.add_outcome(job.id, _ADDED, 6.0, 3.0, study_id=wave_b.id, validate_statement=False)

    comparison = service.compare_waves(wave_a.id, wave_b.id)

    by_statement = {item.statement: item for item in comparison.per_outcome}
    moved = by_statement[_STATEMENT]
    assert moved.score_a == 4.0
    assert moved.score_b == 7.0
    assert moved.delta == 3.0
    assert moved.status == OutcomeComparisonStatus.MOVED
    assert moved.n_a == moved.n_b == 1
    assert comparison.added == [_ADDED]
    assert comparison.dropped == []


def test_a_statement_only_in_wave_two_is_added_and_not_scored_zero() -> None:
    service = _service()
    job = service.add_job("Corn growers", "Grow corn profitably")
    wave_a = _opened_study(service, job.id)
    wave_b = service.next_wave(wave_a.id)
    service.add_outcome(job.id, _ADDED, 6.0, 3.0, study_id=wave_b.id, validate_statement=False)

    comparison = service.compare_waves(wave_a.id, wave_b.id)

    added = next(item for item in comparison.per_outcome if item.statement == _ADDED)
    assert added.status == OutcomeComparisonStatus.ADDED
    # An absent measurement is not a zero.
    assert added.score_a is None
    assert added.delta is None
    assert added.n_a == 0


def test_a_statement_matched_after_the_outcome_is_recreated() -> None:
    service = _service()
    job = service.add_job("Corn growers", "Grow corn profitably")
    wave_a = _opened_study(service, job.id)
    wave_b = service.next_wave(wave_a.id)
    service.add_outcome(job.id, _STATEMENT, 4.0, 4.0, study_id=wave_a.id)
    # Wave B measures the same statement under a brand-new outcome id.
    recreated = service.add_outcome(job.id, _STATEMENT, 9.0, 4.0, study_id=wave_b.id)

    comparison = service.compare_waves(wave_a.id, wave_b.id)

    matched = [item for item in comparison.per_outcome if item.statement == _STATEMENT]
    assert len(matched) == 1, "statement matching must not depend on the outcome id"
    assert matched[0].score_b == 9.0
    assert matched[0].status == OutcomeComparisonStatus.MOVED
    assert comparison.added == []
    assert recreated.statement == _STATEMENT


def test_compare_refuses_studies_from_different_jobs() -> None:
    service = _service()
    first_job = service.add_job("Corn growers", "Grow corn profitably")
    second_job = service.add_job("Wheat growers", "Grow wheat profitably")
    wave_a = _opened_study(service, first_job.id)
    wave_b = _opened_study(service, second_job.id)

    with pytest.raises(StudyJobMismatchError) as excinfo:
        service.compare_waves(wave_a.id, wave_b.id)

    assert wave_a.id in str(excinfo.value)
    assert wave_b.id in str(excinfo.value)


def test_compare_refuses_an_unknown_wave() -> None:
    service = _service()
    job = service.add_job("Corn growers", "Grow corn profitably")
    wave = _opened_study(service, job.id)

    with pytest.raises(StudyNotFoundError):
        service.compare_waves(wave.id, "missing")


def test_close_study_marks_the_wave_closed() -> None:
    service = _service()
    job = service.add_job("Corn growers", "Grow corn profitably")
    wave = _opened_study(service, job.id)

    closed = service.close_study(wave.id)

    assert closed.status == StudyStatus.CLOSED
    assert service.get_study(wave.id).status == StudyStatus.CLOSED


def test_adding_an_outcome_to_an_unknown_study_is_refused() -> None:
    service = _service()
    job = service.add_job("Corn growers", "Grow corn profitably")

    with pytest.raises(StudyNotFoundError):
        service.add_outcome(job.id, _STATEMENT, 5.0, 5.0, study_id="missing")


def test_a_statement_measured_but_unscored_is_reported_unmeasured() -> None:
    service = _service()
    job = service.add_job("Corn growers", "Grow corn profitably")
    wave_a = _opened_study(service, job.id)
    wave_b = service.next_wave(wave_a.id)
    # Recorded in both waves, but never given a score.
    service.repo.add_outcome(
        Outcome(
            id="unscored-a",
            job_id=job.id,
            study_id=wave_a.id,
            statement=_STATEMENT,
            importance=None,
            satisfaction=None,
            opportunity_score=None,
        )
    )
    service.repo.add_outcome(
        Outcome(
            id="unscored-b",
            job_id=job.id,
            study_id=wave_b.id,
            statement=_STATEMENT,
            importance=None,
            satisfaction=None,
            opportunity_score=None,
        )
    )

    comparison = service.compare_waves(wave_a.id, wave_b.id)

    item = next(row for row in comparison.per_outcome if row.statement == _STATEMENT)
    assert item.status == OutcomeComparisonStatus.UNMEASURED
    assert item.score_a is None
    assert item.score_b is None
    assert item.n_a == item.n_b == 1
    assert comparison.added == []
    assert comparison.dropped == []


def test_next_wave_allocates_the_next_number_after_a_manual_wave() -> None:
    """A wave written by another path does not cause a duplicate number."""
    service = _service()
    job = service.add_job("Corn growers", "Grow corn profitably")
    source = _opened_study(service, job.id)
    service.repo.add_study(
        type(source)(
            lineage_id=source.lineage_id,
            job_id=source.job_id,
            name=source.name,
            wave=5,
            frame=source.frame,
        )
    )

    wave = service.next_wave(source.id)

    assert wave.wave == 6
    assert len({s.wave for s in service.list_studies()}) == len(service.list_studies())
