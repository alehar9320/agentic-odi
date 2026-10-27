"""Tests for the core ODIService layer."""

from __future__ import annotations

import pytest
from agentic_odi_core.models import (
    BusinessImpactCategory,
    BusinessValue,
    CustomerValue,
    Direction,
    Job,
    Outcome,
)
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import (
    CustomerOutcomeNotFoundError,
    EvidenceNotFoundError,
    JobNotFoundError,
    ODIService,
    OutcomeNotFoundError,
    StepNotFoundError,
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
    service.add_outcome(
        job.id,
        "Minimize the time it takes to onboard a customer when releasing",
        importance=8.0,
        satisfaction=4.0,
    )
    service.add_step(job.id, "second", order=2)
    service.add_step(job.id, "first", order=1)
    assert [step.name for step in service.get_job_map(job.id)] == ["first", "second"]


def test_add_outcome_computes_opportunity_score(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    outcome = service.add_outcome(
        job.id,
        "Minimize the time it takes to onboard a customer when releasing",
        importance=8.0,
        satisfaction=4.0,
    )
    assert outcome.opportunity_score == 12.0
    assert service.get_outcomes(job.id) == [outcome]


def test_add_outcome_without_scores_has_no_opportunity_score(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    outcome = service.add_outcome(
        job.id,
        "Minimize the time it takes to onboard a customer when releasing",
        importance=5.0,
        satisfaction=5.0,
    )
    assert outcome.opportunity_score == 5.0


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


def test_job_not_found_error_exposes_the_job_id() -> None:
    error = JobNotFoundError("job-1")

    assert error.job_id == "job-1"
    assert str(error) == "job not found: job-1"


def test_add_customer_outcome_accepts_dict_payloads(service: ODIService) -> None:
    job = service.add_job("Onboard customers")
    service.add_outcome(
        job.id,
        "Minimize the time it takes to onboard a customer when releasing",
        importance=8.0,
        satisfaction=4.0,
    )
    step = service.add_step(job.id, "Prepare", order=1)

    outcome = service.add_customer_outcome(
        job.id,
        {
            "direction": "minimize",
            "unit_of_measure": "minutes",
            "object_of_control": "time to onboard a customer",
            "statement": "Minimize the time it takes to onboard a customer",
            "importance": 8.0,
            "satisfaction": 4.0,
        },
        {
            "category": "revenue_growth",
            "statement": "Increase expansion revenue",
        },
        step_id=step.id,
    )

    assert outcome.customer_value.opportunity_score == 12.0
    assert outcome.business_value.category == BusinessImpactCategory.REVENUE_GROWTH
    assert outcome.step_id == step.id


def test_compute_opportunity_delegates_to_the_model(service: ODIService) -> None:
    assert service.compute_opportunity(8.0, 4.0) == 12.0


def test_add_step_requires_existing_job(service: ODIService) -> None:
    with pytest.raises(JobNotFoundError):
        service.add_step("missing", "Step", order=1)


def test_add_outcome_requires_existing_job_and_step(service: ODIService) -> None:
    job = service.add_job("J")
    with pytest.raises(JobNotFoundError):
        service.add_outcome("missing", "Min x", importance=5.0, satisfaction=5.0)
    with pytest.raises(StepNotFoundError):
        service.add_outcome(job.id, "Min x", importance=5.0, satisfaction=5.0, step_id="missing")


def test_update_outcome_recomputes_opportunity_score(service: ODIService) -> None:
    job = service.add_job("J")
    outcome = service.add_outcome(
        job.id,
        "Minimize the time it takes to deploy when releasing",
        importance=5.0,
        satisfaction=5.0,
    )
    assert outcome.opportunity_score == 5.0
    updated = service.update_outcome(outcome.id, {"importance": 8.0})
    assert updated.opportunity_score == 11.0
    updated2 = service.update_outcome(outcome.id, {"satisfaction": 2.0})
    assert updated2.opportunity_score == 14.0


def test_update_outcome_rejects_out_of_range_scores(service: ODIService) -> None:
    job = service.add_job("J")
    outcome = service.add_outcome(
        job.id,
        "Minimize the time it takes to deploy when releasing",
        importance=5.0,
        satisfaction=5.0,
    )
    with pytest.raises(ValueOutOfRangeError):
        service.update_outcome(outcome.id, {"importance": 99})
    stored = service.get_outcome(outcome.id)
    assert stored is not None
    assert stored.importance == 5.0


def test_job_crud_and_cascade(service: ODIService) -> None:
    job = service.add_job("J")
    service.add_outcome(
        job.id,
        "Minimize the time it takes to deploy when releasing",
        importance=5.0,
        satisfaction=5.0,
    )
    service.add_step(job.id, "Step", order=1)
    assert service.update_job(job.id, {"name": "Renamed"}).name == "Renamed"
    assert service.get_step(service.get_job_map(job.id)[0].id) is not None
    service.delete_job(job.id)
    assert service.get_job(job.id) is None
    assert service.get_job_map(job.id) == []
    with pytest.raises(JobNotFoundError):
        service.delete_job(job.id)


def test_update_unknown_ids_raise(service: ODIService) -> None:
    with pytest.raises(JobNotFoundError):
        service.update_job("missing", {"name": "x"})
    with pytest.raises(StepNotFoundError):
        service.update_step("missing", {"name": "x"})
    with pytest.raises(OutcomeNotFoundError):
        service.update_outcome("missing", {"statement": "x"})


def test_add_evidence_resolves_and_validates_links(service: ODIService) -> None:
    job = service.add_job("J")
    service.add_outcome(
        job.id,
        "Minimize the time it takes to deploy when releasing",
        importance=8.0,
        satisfaction=4.0,
    )
    step = service.add_step(job.id, "S", order=1)
    outcome = service.add_outcome(
        job.id,
        "Minimize the time it takes to deploy when releasing",
        importance=8.0,
        satisfaction=4.0,
        step_id=step.id,
    )

    evidence = service.add_evidence(
        source_name="gong",
        source_kind="mcp",
        name="quote",
        content="Lost hours",
        step_id=step.id,
        outcome_id=outcome.id,
    )

    assert evidence.job_id == job.id
    assert service.list_evidence(job_id=job.id) == [evidence]
    with pytest.raises(StepNotFoundError):
        service.add_evidence("s", "mcp", "n", "c", step_id="missing")
    with pytest.raises(OutcomeNotFoundError):
        service.add_evidence("s", "mcp", "n", "c", outcome_id="missing")


def test_evidence_delete_and_promote(service: ODIService) -> None:
    evidence = service.add_evidence(
        source_name="gong",
        source_kind="rest",
        item_type="tool_result",
        name="quote",
        content="Lost 2 hours on deploy",
    )

    job = service.promote_evidence(evidence.id, "job")
    assert isinstance(job, Job)
    assert job.name == "quote"

    outcome = service.promote_evidence(
        evidence.id,
        "outcome",
        job_id=job.id,
        importance=8,
        satisfaction=4,
        statement="Minimize the hours lost to deployment when releasing",
    )
    assert isinstance(outcome, Outcome)
    assert outcome.statement == "Minimize the hours lost to deployment when releasing"
    assert outcome.opportunity_score == 12.0
    with pytest.raises(ValueError):
        service.promote_evidence(evidence.id, "outcome")
    with pytest.raises(ValueError):
        service.promote_evidence(evidence.id, "solution")

    service.delete_evidence(evidence.id)
    with pytest.raises(EvidenceNotFoundError):
        service.delete_evidence(evidence.id)
    with pytest.raises(EvidenceNotFoundError):
        service.promote_evidence(evidence.id, "job")
