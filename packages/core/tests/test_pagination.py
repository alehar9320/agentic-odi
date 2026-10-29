"""Pagination on the list methods of both repositories and the service layer."""

from __future__ import annotations

import pytest
from agentic_odi_core.models import (
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Evidence,
    Job,
    Outcome,
    Step,
)
from agentic_odi_core.repository import InMemoryRepository, page
from agentic_odi_core.services import ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository


def _customer_value(index: int) -> CustomerValue:
    return CustomerValue(
        direction="minimize",
        unit_of_measure="minutes",
        object_of_control="lead time",
        statement=f"co{index}",
        importance=7.0,
        satisfaction=3.0,
    )


def _business_value(index: int) -> BusinessValue:
    return BusinessValue(
        category="operational_efficiency",
        statement=f"bv{index}",
    )


def test_page_slices_and_defaults_to_everything() -> None:
    items = list(range(10))

    assert page(items) == items
    assert page(items, 3) == [0, 1, 2]
    assert page(items, 3, 2) == [2, 3, 4]
    assert page(items, 3, 9) == [9]
    assert page(items, 3, 99) == []


def test_page_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        page([1, 2, 3], 1, -1)
    with pytest.raises(ValueError):
        page([1, 2, 3], -1, 0)


def _seed(repo) -> tuple[Job, list[Step]]:
    job = repo.add_job(Job(name="Deploy", description="Ship a service"))
    steps = [
        repo.add_step(Step(id=f"STEP-{i}", job_id=job.id, name=f"step {i}", order=i))
        for i in range(5)
    ]
    for i, step in enumerate(steps):
        repo.add_outcome(Outcome(id=f"OUT-{i}", job_id=job.id, step_id=step.id, statement=f"o{i}"))
        repo.add_customer_outcome(
            CustomerOutcome(
                id=f"CO-{i}",
                job_id=job.id,
                step_id=step.id,
                customer_value=_customer_value(i),
                business_value=_business_value(i),
            )
        )
        repo.add_evidence(
            Evidence(
                id=f"EV-{i}",
                source_name="Gong",
                source_kind="manual",
                name=f"evidence {i}",
                content=f"evidence {i}",
                job_id=job.id,
                step_id=step.id,
                outcome_id=f"OUT-{i}",
            )
        )
    return job, steps


def test_inmemory_repository_paginates_each_list() -> None:
    repo = InMemoryRepository()
    job, steps = _seed(repo)

    assert len(repo.list_jobs()) == 1
    assert repo.list_jobs(limit=0) == []

    all_steps = repo.get_steps_for_job(job.id)
    assert len(all_steps) == 5
    assert repo.get_steps_for_job(job.id, limit=2) == all_steps[:2]
    assert repo.get_steps_for_job(job.id, limit=2, offset=4) == all_steps[4:]

    assert len(repo.get_outcomes(job.id)) == 5
    assert [o.id for o in repo.get_outcomes(job.id, limit=2, offset=1)] == ["OUT-1", "OUT-2"]
    assert [o.id for o in repo.get_outcomes(job.id, steps[0].id, limit=1)] == ["OUT-0"]

    assert len(repo.list_customer_outcomes(job.id)) == 5
    assert [c.id for c in repo.list_customer_outcomes(job.id, limit=2, offset=3)] == [
        "CO-3",
        "CO-4",
    ]

    assert len(repo.list_evidence(job_id=job.id)) == 5
    assert [e.id for e in repo.list_evidence(job_id=job.id, limit=2, offset=2)] == ["EV-2", "EV-3"]
    assert [e.id for e in repo.list_evidence(step_id=steps[1].id, limit=1)] == ["EV-1"]


def test_sqlite_repository_paginates_each_list(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "page.db"))
    job, _steps = _seed(repo)

    assert len(repo.list_jobs()) == 1
    assert repo.list_jobs(limit=1) == repo.list_jobs()[:1]
    assert repo.list_jobs(limit=1, offset=1) == []

    assert len(repo.get_steps_for_job(job.id)) == 5
    assert len(repo.get_steps_for_job(job.id, limit=2, offset=4)) == 1

    assert [o.id for o in repo.get_outcomes(job.id, limit=2, offset=2)] == ["OUT-2", "OUT-3"]
    assert [c.id for c in repo.list_customer_outcomes(limit=2, offset=2)] == ["CO-2", "CO-3"]
    assert [e.id for e in repo.list_evidence(job_id=job.id, limit=2, offset=2)] == [
        "EV-2",
        "EV-3",
    ]


def test_service_pages_job_map_in_step_order() -> None:
    repo = InMemoryRepository()
    service = ODIService(repo)
    job = service.add_job(name="Deploy")

    # Insert out of order: pagination must still return ascending order.
    for order in (3, 0, 4, 1, 2):
        service.add_step(job_id=job.id, name=f"step {order}", order=order)

    full = service.get_job_map(job.id)
    assert [s.order for s in full] == [0, 1, 2, 3, 4]
    assert [s.order for s in service.get_job_map(job.id, limit=2)] == [0, 1]
    assert [s.order for s in service.get_job_map(job.id, limit=2, offset=3)] == [3, 4]


def test_service_passes_pagination_through() -> None:
    repo = InMemoryRepository()
    service = ODIService(repo)
    job = service.add_job(name="Deploy")
    for i in range(3):
        step = service.add_step(job_id=job.id, name=f"step {i}", order=i)
        service.add_customer_outcome(
            job_id=job.id,
            customer_value=_customer_value(i),
            business_value=_business_value(i),
            step_id=step.id,
        )
        service.add_evidence(
            source_name="Gong",
            source_kind="manual",
            name=f"evidence {i}",
            content=f"evidence {i}",
            job_id=job.id,
            step_id=step.id,
        )

    assert len(service.get_jobs()) == 1
    assert service.get_jobs(limit=1, offset=1) == []
    assert len(service.list_customer_outcomes(limit=1)) == 1
    assert len(service.list_evidence(limit=1, offset=2)) == 1
    assert service.list_evidence(limit=1, offset=3) == []


@pytest.mark.parametrize("bad_kwargs", [{"limit": -1}, {"offset": -1}])
def test_service_surfaces_invalid_pages(bad_kwargs: dict) -> None:
    service = ODIService(InMemoryRepository())
    job = service.add_job(name="Deploy")

    with pytest.raises(ValueError):
        service.get_jobs(**bad_kwargs)
    with pytest.raises(ValueError):
        service.get_job_map(job.id, **bad_kwargs)
    with pytest.raises(ValueError):
        service.list_evidence(**bad_kwargs)
