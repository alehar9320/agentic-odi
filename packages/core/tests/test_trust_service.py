"""The trust read/write service paths: survey import, ranking and staleness."""

from __future__ import annotations

import pytest
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import JobNotFoundError, ODIService


def _service_with_job() -> tuple[ODIService, str]:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Publish a plugin")
    return service, job.id


def _rows(outcome_id: str, count: int, importance: float = 8.0, satisfaction: float = 4.0):
    return [
        {
            "outcome_id": outcome_id,
            "importance": importance,
            "satisfaction": satisfaction,
            "respondent_id": f"r{i}",
        }
        for i in range(count)
    ]


def test_import_survey_lands_a_mean_sample_and_band() -> None:
    service, job_id = _service_with_job()
    outcome = service.add_outcome(
        job_id,
        "Minimize the time to publish when a plugin is ready.",
        7.0,
        3.0,
    )

    updated = service.import_survey(_rows(outcome.id, 40, importance=8.0, satisfaction=4.0))

    landed = updated[outcome.id]
    assert landed.importance == 8.0
    assert landed.satisfaction == 4.0
    assert landed.importance_n == 40
    assert landed.score_method == "survey"
    assert landed.opportunity_low is not None
    assert landed.opportunity_high is not None
    assert landed.opportunity_score is not None
    assert landed.opportunity_low <= landed.opportunity_score <= landed.opportunity_high


def test_import_survey_leaves_the_store_unchanged_when_a_reference_is_unknown() -> None:
    service, job_id = _service_with_job()
    outcome = service.add_outcome(
        job_id,
        "Minimize the time to publish when a plugin is ready.",
        7.0,
        3.0,
    )

    with pytest.raises(ValidationError):
        service.import_survey(_rows("does-not-exist", 40))

    unchanged = service.get_outcome(outcome.id)
    assert unchanged is not None
    assert unchanged.importance == 7.0
    assert unchanged.score_method == "estimate"


def test_rank_outcomes_for_job_partitions_every_outcome() -> None:
    service, job_id = _service_with_job()
    measured = service.add_outcome(
        job_id,
        "Minimize the time to publish when a plugin is ready.",
        8.0,
        4.0,
        importance_n=40,
        satisfaction_n=40,
        score_method="survey",
    )
    thin = service.add_outcome(
        job_id,
        "Minimize the time to recover when a release ships.",
        8.0,
        4.0,
        importance_n=3,
        satisfaction_n=3,
        score_method="survey",
    )
    unscored = service.add_outcome(
        job_id,
        "Minimize the cost to debug when a build breaks.",
        8.0,
        4.0,
    )

    ranking = service.rank_outcomes_for_job(job_id)

    assert ranking["counts"] == {"measured": 1, "thin": 1, "none": 1, "total": 3}
    assert [entry["id"] for entry in ranking["sections"]["measured"]] == [measured.id]
    assert [entry["id"] for entry in ranking["sections"]["thin"]] == [thin.id]
    assert [entry["id"] for entry in ranking["sections"]["none"]] == [unscored.id]


def test_rank_outcomes_for_job_rejects_an_unknown_job() -> None:
    service, _ = _service_with_job()

    with pytest.raises(JobNotFoundError):
        service.rank_outcomes_for_job("no-such-job")


def test_a_score_edit_clears_the_stale_band() -> None:
    service, job_id = _service_with_job()
    outcome = service.add_outcome(
        job_id,
        "Minimize the time to publish when a plugin is ready.",
        8.0,
        4.0,
        importance_n=40,
        satisfaction_n=40,
        score_method="survey",
    )
    banded = service.import_survey(_rows(outcome.id, 40))[outcome.id]
    assert banded.opportunity_low is not None

    edited = service.update_outcome(outcome.id, {"satisfaction": 5.0})

    assert edited.opportunity_low is None
    assert edited.opportunity_high is None
    assert edited.interval_n is None
    assert edited.opportunity_score == 11.0
