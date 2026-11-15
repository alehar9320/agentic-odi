"""Pin the aligned comparison (C3, ALH-34) and its missing-measurement rule.

Readiness choices pinned here:

* The response is **transposed**: one row per metric, one cell per outcome. A
  list of objects per outcome is not comparable, so it is not what we return.
* Column order is the caller's order, and the outcome ids are returned as given
  — a comparison never silently reorders or deduplicates.
* A metric nobody measured renders the literal ``not measured``. A real recorded
  ``0`` stays ``0``; the two are never conflated.
* ``effort`` is shown only when at least one candidate supplies it, because it
  is the one axis the research does not measure.
* The product never declares a winner: there is no "overall" row and no best
  column.
"""

from __future__ import annotations

from typing import Any

import pytest
from agentic_odi_core.brief import NOT_MEASURED
from agentic_odi_core.compare import CompareCandidate, align_outcomes
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import Outcome
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService, OutcomeNotFoundError


@pytest.fixture()
def service() -> ODIService:
    return ODIService(InMemoryRepository())


@pytest.fixture()
def three_outcomes(service: ODIService) -> tuple[ODIService, list[str]]:
    job = service.add_job("Publish a plugin")
    ids = []
    for statement, importance, satisfaction in (
        ("Minimize the time it takes to publish a plugin when a release is ready", 8.0, 3.0),
        ("Minimize the cost of supporting a plugin when it ships", 9.0, 6.0),
        (
            "Minimize the number of steps it takes to publish a plugin when a release is ready",
            6.0,
            5.0,
        ),
    ):
        outcome = service.add_outcome(job.id, statement, importance, satisfaction)
        ids.append(outcome.id)
    step = service.add_step(job.id, "Execute", 5)
    for outcome_id in ids:
        service.update_outcome(outcome_id, {"step_id": step.id})
    return service, ids


def _candidate(**overrides: Any) -> CompareCandidate:
    base: dict[str, Any] = dict(
        outcome_id="o-1",
        statement="Minimize the time it takes to publish a plugin when a release is ready",
        score=13.0,
        importance=8.0,
        satisfaction=3.0,
        stage="Execute",
        evidence_count=4,
        sample_size=12,
    )
    base.update(overrides)
    return CompareCandidate(**base)


def test_columns_follow_the_given_order() -> None:
    comparison = align_outcomes(
        [
            _candidate(outcome_id="o-1"),
            _candidate(outcome_id="o-2"),
            _candidate(outcome_id="o-3"),
        ]
    )
    assert comparison.columns == ("o-1", "o-2", "o-3")


def test_every_row_has_one_cell_per_column() -> None:
    comparison = align_outcomes([_candidate(outcome_id="o-1"), _candidate(outcome_id="o-2")])
    for row in comparison.rows:
        assert len(row.cells) == 2


def test_a_missing_metric_reads_not_measured_while_zero_stays_zero() -> None:
    comparison = align_outcomes(
        [
            _candidate(outcome_id="o-1", score=None, sample_size=None),
            _candidate(outcome_id="o-2", score=0.0, sample_size=0),
        ]
    )
    score = next(row for row in comparison.rows if row.metric == "score")
    assert score.cells == (NOT_MEASURED, "0")
    sample = next(row for row in comparison.rows if row.metric == "sample_size")
    assert sample.cells == (NOT_MEASURED, "0")


def test_band_is_unscored_when_the_score_is_missing() -> None:
    comparison = align_outcomes([_candidate(outcome_id="o-1", score=None)])
    band = next(row for row in comparison.rows if row.metric == "band")
    assert band.cells == ("unscored",)


def test_effort_row_appears_only_when_supplied() -> None:
    without = align_outcomes([_candidate(), _candidate(outcome_id="o-2")])
    assert all(row.metric != "effort" for row in without.rows)

    with_effort = align_outcomes([_candidate(effort="2 weeks"), _candidate(outcome_id="o-2")])
    effort = next(row for row in with_effort.rows if row.metric == "effort")
    assert effort.cells == ("2 weeks", NOT_MEASURED)


def test_there_is_no_overall_or_winner_row() -> None:
    comparison = align_outcomes([_candidate(), _candidate(outcome_id="o-2")])
    metrics = {row.metric for row in comparison.rows}
    assert "overall" not in metrics
    assert "winner" not in metrics


def test_statements_are_returned_in_column_order() -> None:
    comparison = align_outcomes(
        [
            _candidate(outcome_id="o-1", statement="Minimize A when ready"),
            _candidate(outcome_id="o-2", statement="Minimize B when ready"),
        ]
    )
    assert comparison.statements == ("Minimize A when ready", "Minimize B when ready")


def test_service_aligns_two_outcomes_in_the_given_order(three_outcomes) -> None:
    service, ids = three_outcomes
    comparison = service.compare_outcomes([ids[1], ids[0]])
    assert comparison.columns == (ids[1], ids[0])


def test_service_aligns_three_outcomes(three_outcomes) -> None:
    service, ids = three_outcomes
    comparison = service.compare_outcomes(ids)
    assert comparison.columns == tuple(ids)
    for row in comparison.rows:
        assert len(row.cells) == 3


def test_service_refuses_a_single_id_naming_the_minimum(three_outcomes) -> None:
    service, ids = three_outcomes
    with pytest.raises(ValidationError) as excinfo:
        service.compare_outcomes([ids[0]])
    assert "at least 2" in str(excinfo.value)


def test_service_refuses_a_fourth_id_naming_the_limit(three_outcomes) -> None:
    service, ids = three_outcomes
    with pytest.raises(ValidationError) as excinfo:
        service.compare_outcomes([*ids, ids[0] + "-x"])
    assert "at most 3" in str(excinfo.value)


def test_service_refuses_duplicate_ids(three_outcomes) -> None:
    service, ids = three_outcomes
    with pytest.raises(ValidationError) as excinfo:
        service.compare_outcomes([ids[0], ids[0]])
    assert "distinct" in str(excinfo.value)


def test_service_refuses_an_unknown_id_before_returning_a_partial_table(three_outcomes) -> None:
    service, ids = three_outcomes
    with pytest.raises(OutcomeNotFoundError):
        service.compare_outcomes([ids[0], "does-not-exist"])


def test_service_reports_the_stage_and_evidence_count(three_outcomes) -> None:
    service, ids = three_outcomes
    comparison = service.compare_outcomes(ids[:2])
    stage = next(row for row in comparison.rows if row.metric == "stage")
    assert stage.cells == ("Execute", "Execute")
    evidence = next(row for row in comparison.rows if row.metric == "evidence_count")
    assert evidence.cells == ("0", "0")


def test_service_leaves_repository_state_unchanged(three_outcomes) -> None:
    service, ids = three_outcomes
    before = dict(service.repo.outcomes)
    service.compare_outcomes(ids)
    assert service.repo.outcomes == before


def test_service_renders_not_measured_for_an_unscored_outcome(service: ODIService) -> None:
    job = service.add_job("Publish a plugin")
    scored = service.add_outcome(
        job.id, "Minimize the time it takes to publish a plugin when a release is ready", 8.0, 3.0
    )
    unscored = service.repo.add_outcome(
        Outcome(
            job_id=job.id,
            statement="Minimize the number of steps it takes to publish a plugin when a release is ready",
        )
    )
    comparison = service.compare_outcomes([scored.id, unscored.id])
    score = next(row for row in comparison.rows if row.metric == "score")
    assert score.cells == ("13", NOT_MEASURED)
