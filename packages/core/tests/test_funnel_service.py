"""The funnel is counted by the paths a person actually walks.

A counter nobody increments is a table of zeros, so these tests drive the real
service methods and assert what the log says afterwards.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.funnel import read_counts
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository

#: A desired-outcome statement has to pass the domain validator, so the funnel
#: tests use a well-formed one rather than fighting the guard for no reason.
_STATEMENT = "Minimize the time it takes to onboard a customer when they sign up."


@pytest.fixture
def service(tmp_path):
    repo = SQLiteRepository(str(tmp_path / "odi.db"))
    yield ODIService(repo)
    repo.store.close()


def _counts(carrier) -> dict[str, int]:
    return {name: view["counts"] for name, view in read_counts(carrier).items()}


def test_creating_an_outcome_records_the_first_outcome(service) -> None:
    job = service.add_job("Onboard customers")

    service.add_outcome(job.id, _STATEMENT)

    assert _counts(service)["first_outcome"] == 1


def test_creating_a_second_outcome_does_not_repeat_the_milestone(service) -> None:
    job = service.add_job("Onboard customers")

    service.add_outcome(job.id, _STATEMENT)
    service.add_outcome(
        job.id, "Minimize the number of failed payments a customer hits when they retry."
    )

    assert _counts(service)["first_outcome"] == 1


def test_an_unscored_outcome_records_no_score(service) -> None:
    job = service.add_job("Onboard customers")

    service.add_outcome(job.id, _STATEMENT)

    assert _counts(service)["first_score"] == 0


def test_creating_an_outcome_with_both_scores_records_the_first_score(service) -> None:
    job = service.add_job("Onboard customers")

    service.add_outcome(job.id, _STATEMENT, importance=8.0, satisfaction=2.0)

    assert _counts(service)["first_score"] == 1


def test_scoring_an_existing_outcome_records_the_first_score(service) -> None:
    job = service.add_job("Onboard customers")
    outcome = service.add_outcome(job.id, _STATEMENT)

    service.update_outcome(outcome.id, {"importance": 9.0, "satisfaction": 3.0})

    assert _counts(service)["first_score"] == 1


def test_scoring_twice_records_the_score_milestone_once(service) -> None:
    job = service.add_job("Onboard customers")
    outcome = service.add_outcome(job.id, _STATEMENT)

    service.update_outcome(outcome.id, {"importance": 9.0, "satisfaction": 3.0})
    service.update_outcome(outcome.id, {"importance": 6.0, "satisfaction": 6.0})

    assert _counts(service)["first_score"] == 1


def test_an_update_that_does_not_score_the_outcome_records_no_score(service) -> None:
    job = service.add_job("Onboard customers")
    outcome = service.add_outcome(job.id, _STATEMENT)

    service.update_outcome(
        outcome.id,
        {"statement": "Minimize the time it takes to activate a customer when they sign up."},
    )

    assert _counts(service)["first_score"] == 0


def test_a_service_without_an_event_log_still_creates_its_outcome() -> None:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Onboard customers")

    outcome = service.add_outcome(job.id, _STATEMENT, importance=8.0, satisfaction=2.0)

    assert outcome.opportunity_score is not None
    assert all(count == 0 for count in _counts(service).values())
