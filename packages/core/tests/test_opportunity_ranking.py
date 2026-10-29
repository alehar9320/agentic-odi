"""Pin the opportunity leaderboard and its served/underserved buckets."""

from __future__ import annotations

from agentic_odi_core.evaluation import classify_opportunity
from agentic_odi_core.models import Outcome
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService

# (importance, satisfaction) -> opportunity score
LOW = (5, 5)  # 5
APPROPRIATE = (8, 6)  # 10
HIGH = (9, 3)  # 15


def _ranked_scores() -> list[float | None]:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Publish a plugin")
    for label, (importance, satisfaction) in (
        ("low", LOW),
        ("high", HIGH),
        ("appropriate", APPROPRIATE),
    ):
        service.add_outcome(
            job.id,
            f"Minimize the time to {label} when a customer installs the plugin.",
            importance,
            satisfaction,
        )
    return [outcome.opportunity_score for outcome in service.get_outcomes(job.id)]


def test_outcomes_are_ranked_by_opportunity_score():
    assert _ranked_scores() == [15.0, 10.0, 5.0]


def test_unscored_outcomes_sort_after_scored_ones():
    repository = InMemoryRepository()
    service = ODIService(repository)
    job = service.add_job("Publish a plugin")
    repository.add_outcome(
        Outcome(
            job_id=job.id,
            statement="Minimize the time to install when a customer starts.",
            importance=5,
            satisfaction=5,
            opportunity_score=None,
        )
    )
    service.add_outcome(
        job.id,
        "Minimize the time to publish when a customer ships.",
        *HIGH,
    )

    scores = [outcome.opportunity_score for outcome in service.get_outcomes(job.id)]

    assert scores == [15.0, None]


def test_opportunity_scores_are_bucketed():
    assert classify_opportunity(10.1) == "underserved"
    assert classify_opportunity(10.0) == "appropriate"
    assert classify_opportunity(9.9) == "overserved"
    assert classify_opportunity(None) == "unscored"
