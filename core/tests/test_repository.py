"""Tests for the in-memory Repository implementation."""

from __future__ import annotations

import pytest

from core.models import (
    BusinessImpactCategory,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Direction,
    Job,
    Outcome,
    Step,
)
from core.repository import InMemoryRepository


def _customer_outcome(outcome_id: str, job_id: str = "job-1") -> CustomerOutcome:
    return CustomerOutcome(
        id=outcome_id,
        job_id=job_id,
        customer_value=CustomerValue(
            direction=Direction.MINIMIZE,
            unit_of_measure="minutes",
            object_of_control="time to onboard",
            statement="Minimize the time it takes to onboard",
            importance=8.0,
            satisfaction=4.0,
        ),
        business_value=BusinessValue(
            category=BusinessImpactCategory.COST_REDUCTION,
            statement="Reduce support cost",
        ),
    )


def test_get_outcomes_filters_by_step() -> None:
    repo = InMemoryRepository()
    repo.add_outcome(Outcome(id="o-1", job_id="job-1", step_id="step-1", statement="one"))
    repo.add_outcome(Outcome(id="o-2", job_id="job-1", step_id="step-2", statement="two"))

    assert [o.id for o in repo.get_outcomes("job-1", step_id="step-1")] == ["o-1"]
    assert [o.id for o in repo.get_outcomes("job-1")] == ["o-1", "o-2"]


def test_list_customer_outcomes_without_filter_returns_all() -> None:
    repo = InMemoryRepository()
    repo.add_customer_outcome(_customer_outcome("co-1", "job-1"))
    repo.add_customer_outcome(_customer_outcome("co-2", "job-2"))

    assert [co.id for co in repo.list_customer_outcomes()] == ["co-1", "co-2"]
    assert [co.id for co in repo.list_customer_outcomes("job-2")] == ["co-2"]


def test_update_customer_outcome_returns_none_for_missing_id() -> None:
    assert InMemoryRepository().update_customer_outcome("missing", {}) is None


def test_update_customer_outcome_rejects_invalid_updates() -> None:
    repo = InMemoryRepository()
    repo.add_customer_outcome(_customer_outcome("co-1"))

    with pytest.raises(ValueError):
        repo.update_customer_outcome("co-1", {"customer_value": {"importance": 99.0}})


def test_delete_customer_outcome_reports_missing_id() -> None:
    assert InMemoryRepository().delete_customer_outcome("missing") is False


def test_clear_removes_all_entities() -> None:
    repo = InMemoryRepository()
    job = repo.add_job(Job(id="job-1", name="Onboard customers"))
    repo.add_step(Step(id="step-1", job_id=job.id, name="Prepare", order=1))
    repo.add_outcome(Outcome(id="o-1", job_id=job.id, statement="Minimize time"))
    repo.add_customer_outcome(_customer_outcome("co-1", job.id))

    repo.clear()

    assert repo.list_jobs() == []
    assert repo.get_steps_for_job(job.id) == []
    assert repo.get_outcomes(job.id) == []
    assert repo.list_customer_outcomes() == []
