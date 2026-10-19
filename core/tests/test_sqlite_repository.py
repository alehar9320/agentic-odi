"""Tests for the SQLite-backed repository and its event-sourced snapshot."""

from __future__ import annotations

import sqlite3

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
from core.sqlite_repository import SQLiteRepository


def _customer_outcome(job_id: str, *, outcome_id: str = "co-1") -> CustomerOutcome:
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
            category=BusinessImpactCategory.REVENUE_GROWTH,
            statement="Increase expansion revenue",
        ),
    )


def test_add_and_read_back_every_entity(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    job = repo.add_job(Job(id="job-1", name="Onboard customers"))
    step = repo.add_step(Step(id="step-1", job_id="job-1", name="Prepare", order=1))
    outcome = repo.add_outcome(
        Outcome(id="outcome-1", job_id="job-1", step_id="step-1", statement="Minimize time")
    )
    customer_outcome = repo.add_customer_outcome(_customer_outcome("job-1"))

    assert repo.list_jobs() == [job]
    assert repo.get_job("job-1") == job
    assert repo.get_job("missing") is None
    assert repo.get_steps_for_job("job-1") == [step]
    assert repo.get_outcomes("job-1") == [outcome]
    assert repo.get_outcomes("job-1", step_id="step-1") == [outcome]
    assert repo.get_outcomes("job-1", step_id="other") == []
    assert repo.get_customer_outcome("co-1") == customer_outcome
    assert repo.get_customer_outcome("missing") is None
    assert repo.list_customer_outcomes() == [customer_outcome]
    assert repo.list_customer_outcomes("job-1") == [customer_outcome]
    assert repo.list_customer_outcomes("other") == []


def test_snapshot_reloads_every_event_type_from_disk(tmp_path) -> None:
    db_path = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path)
    repo.add_job(Job(id="job-1", name="Onboard customers"))
    repo.add_step(Step(id="step-1", job_id="job-1", name="Prepare", order=1))
    repo.add_outcome(Outcome(id="outcome-1", job_id="job-1", statement="Minimize time"))
    created = repo.add_customer_outcome(_customer_outcome("job-1"))
    customer_value = created.customer_value.model_dump()
    customer_value["importance"] = 9.0
    repo.update_customer_outcome("co-1", {"customer_value": customer_value})

    reloaded = SQLiteRepository(db_path)

    assert reloaded.get_job("job-1") is not None
    assert reloaded.get_steps_for_job("job-1")[0].name == "Prepare"
    assert reloaded.get_outcomes("job-1")[0].statement == "Minimize time"
    reloaded_outcome = reloaded.get_customer_outcome("co-1")
    assert reloaded_outcome is not None
    assert reloaded_outcome.customer_value.importance == 9.0


def test_snapshot_drops_customer_outcomes_after_delete_event(tmp_path) -> None:
    db_path = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path)
    repo.add_customer_outcome(_customer_outcome("job-1"))
    assert repo.delete_customer_outcome("co-1") is True

    reloaded = SQLiteRepository(db_path)

    assert reloaded.get_customer_outcome("co-1") is None


def test_snapshot_skips_invalid_update_events(tmp_path) -> None:
    db_path = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path)
    repo.add_customer_outcome(_customer_outcome("job-1"))
    repo.store.append(
        "CUSTOMER_OUTCOME_UPDATED",
        {"id": "co-1", "updates": {"customer_value": {"importance": 99.0}}},
    )

    reloaded = SQLiteRepository(db_path)

    reloaded_outcome = reloaded.get_customer_outcome("co-1")
    assert reloaded_outcome is not None
    assert reloaded_outcome.customer_value.importance == 8.0


def test_update_customer_outcome_returns_none_for_missing_or_invalid(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"))

    assert repo.update_customer_outcome("missing", {}) is None

    repo.add_customer_outcome(_customer_outcome("job-1"))
    assert repo.update_customer_outcome("co-1", {"customer_value": {"importance": 99.0}}) is None


def test_delete_customer_outcome_reports_missing_id(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"))

    assert repo.delete_customer_outcome("missing") is False


def test_clear_removes_all_entities_and_events(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    repo.add_job(Job(id="job-1", name="Onboard customers"))
    repo.add_customer_outcome(_customer_outcome("job-1"))

    repo.clear()

    assert repo.list_jobs() == []
    assert repo.list_customer_outcomes() == []
    assert repo.store.get_stream() == []


def test_default_path_uses_environment_override(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "nested" / "odi.db"
    monkeypatch.setenv("AGENTIC_ODI_DB", str(db_path))

    repo = SQLiteRepository()

    assert db_path.exists()
    assert repo.list_jobs() == []


def test_snapshot_ignores_unknown_event_types(tmp_path) -> None:
    db_path = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db_path)
    repo.store.append("SOMETHING_ELSE", {"id": "x"})

    reloaded = SQLiteRepository(db_path)

    assert reloaded.list_jobs() == []


def test_closing_the_store_prevents_further_reads(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    repo.store.close()

    with pytest.raises(sqlite3.ProgrammingError):
        repo.store.get_stream()
