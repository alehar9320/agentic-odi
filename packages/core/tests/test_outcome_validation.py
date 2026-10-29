"""The outcome statement guard is enforced when an outcome is captured."""

from __future__ import annotations

import pytest
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import InvalidOutcomeStatementError, ODIService


@pytest.fixture
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def test_add_outcome_rejects_a_vague_statement_with_its_issues(
    service: ODIService,
) -> None:
    job = service.add_job("Onboard customers")

    with pytest.raises(InvalidOutcomeStatementError) as raised:
        service.add_outcome(job.id, "Make it faster", importance=8.0, satisfaction=4.0)

    assert raised.value.issues
    assert any("Minimize" in issue or "Maximize" in issue for issue in raised.value.issues)
    assert service.get_outcomes(job.id) == []


def test_add_outcome_accepts_a_well_formed_statement(service: ODIService) -> None:
    job = service.add_job("Onboard customers")

    outcome = service.add_outcome(
        job.id,
        "Minimize the time it takes to onboard a customer when they sign up.",
        importance=8.0,
        satisfaction=4.0,
    )

    assert outcome.statement.startswith("Minimize the time")
    assert service.get_outcomes(job.id) == [outcome]


def test_seeded_data_can_opt_out_of_the_statement_guard(service: ODIService) -> None:
    job = service.add_job("Onboard customers")

    outcome = service.add_outcome(
        job.id,
        "Make it faster",
        importance=8.0,
        satisfaction=4.0,
        validate_statement=False,
    )

    assert outcome.statement == "Make it faster"
