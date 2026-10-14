"""Tests for the core ODIService layer."""

from __future__ import annotations

import pytest

from core.models import BusinessImpactCategory, BusinessValue, CustomerValue, Direction
from core.repository import InMemoryRepository
from core.services import (
    CustomerOutcomeNotFoundError,
    ODIService,
    ValueOutOfRangeError,
)


@pytest.fixture
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _customer_value() -> CustomerValue:
    return CustomerValue(
        direction=Direction.MINIMIZE,
        unit_of_measure="minutes",
        object_of_control="time to onboard a customer",
        statement="Minimize the time it takes to onboard a customer",
        importance=8.0,
        satisfaction=4.0,
    )


def _business_value() -> BusinessValue:
    return BusinessValue(
        category=BusinessImpactCategory.REVENUE_GROWTH,
        statement="Increase expansion revenue",
    )


def test_add_and_get_job(service: ODIService) -> None:
    job = service.add_job("Onboard customers", description="Reduce time to first value")
    assert service.get_job(job.id) == job
    assert service.get_jobs() == [job]


def test_get_job_returns_none_for_unknown_id(service: ODIService) -> None:
    assert service.get_job("missing") is None


def test_job_map_is_sorted_by_order(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    service.add_step(job.id, "second", order=2)
    service.add_step(job.id, "first", order=1)
    assert [step.name for step in service.get_job_map(job.id)] == ["first", "second"]


def test_add_outcome_computes_opportunity_score(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    outcome = service.add_outcome(
        job.id, "Minimize onboarding time", importance=8.0, satisfaction=4.0
    )
    assert outcome.opportunity_score == 12.0
    assert service.get_outcomes(job.id) == [outcome]


def test_add_outcome_without_scores_has_no_opportunity_score(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    outcome = service.add_outcome(job.id, "Minimize onboarding time")
    assert outcome.opportunity_score is None


@pytest.mark.parametrize(("importance", "satisfaction"), [(0.5, 5.0), (5.0, 11.0)])
def test_add_outcome_rejects_out_of_range_scores(
    service: ODIService, importance: float, satisfaction: float
) -> None:
    job = service.add_job("Onboard customers")
    with pytest.raises(ValueOutOfRangeError):
        service.add_outcome(
            job.id, "Minimize onboarding time", importance=importance, satisfaction=satisfaction
        )


def test_customer_outcome_crud(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    created = service.add_customer_outcome(job.id, _customer_value(), _business_value())
    assert service.get_customer_outcome(created.id) == created
    assert service.list_customer_outcomes(job.id) == [created]

    updated = service.update_customer_outcome(
        created.id,
        {
            "business_value": {
                "category": "cost_reduction",
                "statement": "Reduce support cost",
            }
        },
    )
    assert updated.business_value.statement == "Reduce support cost"

    service.delete_customer_outcome(created.id)
    assert service.list_customer_outcomes(job.id) == []


def test_customer_outcome_not_found_errors(service: ODIService) -> None:
    with pytest.raises(CustomerOutcomeNotFoundError):
        service.get_customer_outcome("missing")
    with pytest.raises(CustomerOutcomeNotFoundError):
        service.update_customer_outcome("missing", {})
    with pytest.raises(CustomerOutcomeNotFoundError):
        service.delete_customer_outcome("missing")
