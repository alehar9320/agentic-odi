"""Tests for the in-memory Repository implementation."""

from __future__ import annotations

import pytest
from agentic_odi_core.models import (
    BusinessImpactCategory,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Direction,
    Evidence,
    Job,
    Outcome,
    Step,
)
from agentic_odi_core.repository import InMemoryRepository


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


def _repo_with_graph() -> InMemoryRepository:
    repo = InMemoryRepository()
    repo.add_job(Job(id="j1", name="Job"))
    repo.add_step(Step(id="s1", job_id="j1", name="Step", order=1))
    repo.add_outcome(Outcome(id="o1", job_id="j1", step_id="s1", statement="Min x"))
    return repo


def _linked_customer_outcome(id: str, job_id: str, step_id: str | None = None) -> CustomerOutcome:
    return CustomerOutcome(
        id=id,
        job_id=job_id,
        step_id=step_id,
        customer_value=CustomerValue(
            direction=Direction.MINIMIZE,
            unit_of_measure="minutes",
            object_of_control="support team",
            statement="Minimize resolution time",
            importance=9.0,
            satisfaction=3.0,
        ),
        business_value=BusinessValue(
            category=BusinessImpactCategory.COST_REDUCTION,
            statement="Reduce support cost",
        ),
    )


def test_get_step_and_get_outcome():
    repo = _repo_with_graph()
    assert repo.get_step("s1").name == "Step"  # type: ignore[union-attr]
    assert repo.get_outcome("o1").statement == "Min x"  # type: ignore[union-attr]
    assert repo.get_step("missing") is None


def test_update_job_merges_and_returns_none_when_missing():
    repo = _repo_with_graph()
    updated = repo.update_job("j1", {"name": "Renamed"})
    assert updated is not None and updated.name == "Renamed"
    assert repo.update_job("nope", {"name": "x"}) is None


def test_delete_job_cascades_dependents():
    repo = _repo_with_graph()
    assert repo.delete_job("j1") is True
    assert repo.get_job("j1") is None
    assert repo.get_step("s1") is None
    assert repo.get_outcome("o1") is None
    assert repo.delete_job("j1") is False


def test_delete_step_cascades_its_outcomes():
    repo = _repo_with_graph()
    repo.add_outcome(Outcome(id="o2", job_id="j1", statement="Unbound"))
    assert repo.delete_step("s1") is True
    assert repo.get_step("s1") is None
    assert repo.get_outcome("o1") is None
    assert repo.get_outcome("o2") is not None


def test_update_step_and_update_outcome_merge_or_return_none():
    repo = _repo_with_graph()
    updated_step = repo.update_step("s1", {"name": "Renamed step"})
    assert updated_step is not None and updated_step.name == "Renamed step"
    updated_outcome = repo.update_outcome("o1", {"statement": "Max y"})
    assert updated_outcome is not None and updated_outcome.statement == "Max y"
    assert repo.update_step("nope", {"name": "x"}) is None
    assert repo.update_outcome("nope", {"statement": "x"}) is None


def test_delete_outcome_and_delete_step_return_false_when_missing():
    repo = _repo_with_graph()
    assert repo.delete_outcome("nope") is False
    assert repo.delete_step("nope") is False
    assert repo.delete_outcome("o1") is True
    assert repo.get_outcome("o1") is None


def test_delete_job_cascades_customer_outcomes():
    repo = _repo_with_graph()
    repo.add_customer_outcome(_linked_customer_outcome("co1", job_id="j1", step_id="s1"))
    repo.add_customer_outcome(_linked_customer_outcome("co2", job_id="other"))
    assert repo.delete_job("j1") is True
    assert repo.get_customer_outcome("co1") is None
    assert repo.get_customer_outcome("co2") is not None


def test_delete_step_cascades_customer_outcomes():
    repo = _repo_with_graph()
    repo.add_customer_outcome(_linked_customer_outcome("co1", job_id="j1", step_id="s1"))
    repo.add_customer_outcome(_linked_customer_outcome("co2", job_id="j1"))
    assert repo.delete_step("s1") is True
    assert repo.get_customer_outcome("co1") is None
    assert repo.get_customer_outcome("co2") is not None
    assert repo.get_customer_outcome("co1") is None
    assert repo.get_customer_outcome("co2") is not None


def _evidence(id: str, **overrides) -> Evidence:
    payload = {
        "id": id,
        "source_name": "gong",
        "source_kind": "mcp",
        "item_type": "resource",
        "name": "feedback",
        "content": "Lost hours on deploy",
    }
    payload.update(overrides)
    return Evidence(**payload)


def test_evidence_crud_and_filters():
    repo = _repo_with_graph()
    repo.add_evidence(_evidence("e1", job_id="j1", step_id="s1", outcome_id="o1"))
    repo.add_evidence(_evidence("e2", job_id="j1"))
    assert repo.get_evidence("e1") is not None
    assert len(repo.list_evidence(job_id="j1")) == 2
    assert [item.id for item in repo.list_evidence(step_id="s1")] == ["e1"]
    assert [item.id for item in repo.list_evidence(outcome_id="o1")] == ["e1"]
    assert repo.delete_evidence("e1") is True
    assert repo.delete_evidence("e1") is False
    assert repo.get_evidence("e1") is None


def test_delete_job_cascades_evidence():
    repo = _repo_with_graph()
    repo.add_evidence(_evidence("e1", job_id="j1", step_id="s1", outcome_id="o1"))
    repo.add_evidence(_evidence("e2", job_id="j1"))
    repo.add_evidence(_evidence("e3", job_id="other"))
    assert repo.delete_job("j1") is True
    assert repo.get_evidence("e1") is None
    assert repo.get_evidence("e2") is None
    assert repo.get_evidence("e3") is not None


def test_delete_outcome_cascades_evidence():
    repo = _repo_with_graph()
    repo.add_evidence(_evidence("e1", job_id="j1", outcome_id="o1"))
    assert repo.delete_outcome("o1") is True
    assert repo.get_evidence("e1") is None
