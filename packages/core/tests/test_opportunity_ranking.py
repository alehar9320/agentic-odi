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
            id="unscored",
            job_id=job.id,
            statement="Minimize the time to install when a customer starts.",
            importance=None,
            satisfaction=None,
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


def test_rank_by_opportunity_low_orders_by_the_band_low_end():
    from agentic_odi_core.repository import rank_outcomes

    a = Outcome(
        job_id="j",
        statement="Minimize the time to a when a customer installs the plugin.",
        importance=8.0,
        satisfaction=5.0,
        opportunity_score=11.0,
        opportunity_low=10.0,
        opportunity_high=12.0,
    )
    b = Outcome(
        job_id="j",
        statement="Minimize the time to b when a customer installs the plugin.",
        importance=9.0,
        satisfaction=3.0,
        opportunity_score=15.0,
        opportunity_low=12.0,
        opportunity_high=18.0,
    )

    ranked = rank_outcomes([a, b], by="opportunity_low")
    assert [o.id for o in ranked] == [b.id, a.id]


def test_rank_by_opportunity_low_falls_back_to_the_point_score_without_a_band():
    from agentic_odi_core.repository import rank_outcomes

    banded = Outcome(
        job_id="j",
        statement="Minimize the time to a when a customer installs the plugin.",
        importance=8.0,
        satisfaction=5.0,
        opportunity_score=11.0,
        opportunity_low=13.0,
        opportunity_high=14.0,
    )
    bare = Outcome(
        job_id="j",
        statement="Minimize the time to b when a customer installs the plugin.",
        importance=9.0,
        satisfaction=3.0,
        opportunity_score=15.0,
    )

    ranked = rank_outcomes([banded, bare], by="opportunity_low")
    # bare falls back to 15.0 > banded low 13.0, so bare ranks first
    assert [o.id for o in ranked] == [bare.id, banded.id]


def test_rank_outcomes_rejects_an_unknown_key():
    import pytest
    from agentic_odi_core.repository import rank_outcomes

    with pytest.raises(ValueError):
        rank_outcomes([], by="midpoint")
