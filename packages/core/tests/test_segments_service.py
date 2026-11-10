"""Tests for the Stage 5 and Stage 6 service surface."""

from __future__ import annotations

import pytest
from agentic_odi_core import (
    InMemoryRepository,
    JobNotFoundError,
    NoStrategyEvidenceError,
    ODIService,
    Segment,
    SegmentNotFoundError,
    SegmentVerdict,
    StrategyKind,
)
from agentic_odi_core.errors import ValidationError


def _segment(job_id: str, outcome_ids: list[str]) -> Segment:
    return Segment(
        job_id=job_id,
        outcome_ids=outcome_ids,
        name="Platform engineers, gather the values",
        people="Platform engineers",
        job_statement="Rotate a leaked secret without an outage",
        rationale="2 outcomes on the gather step.",
        confidence=0.75,
    )


@pytest.fixture
def service() -> ODIService:
    return ODIService(InMemoryRepository())


@pytest.fixture
def seeded(service: ODIService) -> tuple[ODIService, str]:
    job = service.add_job("Rotate a leaked secret")
    step = service.add_step(job.id, "Gather the current values", order=1, allow_empty_job_map=True)
    service.add_outcome(
        job.id,
        statement="Minimize the time it takes to rotate the secret when it leaks",
        importance=9,
        satisfaction=2,
        step_id=step.id,
    )
    service.add_outcome(
        job.id,
        statement="Minimize the number of missed values after rotation",
        importance=8,
        satisfaction=3,
        step_id=step.id,
    )
    verify = service.add_step(job.id, "Verify the new value", order=2, allow_empty_job_map=True)
    service.add_outcome(
        job.id,
        statement="Minimize the time it takes to verify the new value when deploying",
        importance=5,
        satisfaction=5,
        step_id=verify.id,
    )
    return service, job.id


def test_segment_market_clusters_and_persists(seeded: tuple[ODIService, str]) -> None:
    service, job_id = seeded

    segments = service.segment_market()

    assert len(segments) == 1
    assert segments[0].verdict is SegmentVerdict.UNDERSERVED
    assert service.list_segments() == segments
    assert service.list_segments(job_id=job_id) == segments


def test_segment_market_scopes_to_one_job(seeded: tuple[ODIService, str]) -> None:
    service, job_id = seeded
    other = service.add_job("Answer a security questionnaire")

    assert [s.job_id for s in service.segment_market(job_id=other.id)] == []
    assert [s.job_id for s in service.segment_market(job_id=job_id)] == [job_id]


def test_segment_market_rejects_a_job_that_is_not_stored(service: ODIService) -> None:
    with pytest.raises(JobNotFoundError):
        service.segment_market(job_id="nope")


def test_re_running_segmentation_updates_the_segment_not_duplicates_it(
    seeded: tuple[ODIService, str],
) -> None:
    service, _ = seeded

    first = service.segment_market()
    second = service.segment_market()

    assert [s.id for s in second] == [s.id for s in first]
    assert len(service.list_segments()) == 1


def test_a_segment_of_one_is_refused_as_a_hypothesis(seeded: tuple[ODIService, str]) -> None:
    service, job_id = seeded
    outcome = service.add_outcome(
        job_id,
        statement="Minimize the time it takes to verify the value when deploying",
        importance=6,
        satisfaction=6,
    )

    with pytest.raises(ValidationError, match="at least 2 outcomes"):
        service.save_segment(_segment(job_id, [outcome.id]))


def test_a_segment_may_only_cite_outcomes_the_store_has(seeded: tuple[ODIService, str]) -> None:
    service, job_id = seeded
    existing = service.segment_market()[0].outcome_ids

    with pytest.raises(ValidationError, match="do not exist"):
        service.save_segment(_segment(job_id, [*existing, "ghost"]))


def test_propose_strategy_persists_the_recommendation(seeded: tuple[ODIService, str]) -> None:
    service, _ = seeded
    service.segment_market()

    strategy = service.propose_strategy()

    assert strategy.kind is StrategyKind.DIFFERENTIATED
    assert len(strategy.rejected) == 2
    assert service.get_strategy() == strategy
    assert service.list_strategies(segment_id=strategy.segment_id) == [strategy]


def test_re_proposing_updates_the_same_strategy_record(seeded: tuple[ODIService, str]) -> None:
    service, _ = seeded
    service.segment_market()

    first = service.propose_strategy()
    second = service.propose_strategy()

    assert first.id == second.id
    assert len(service.list_strategies()) == 1


def test_propose_strategy_refuses_to_invent_a_bet(seeded: tuple[ODIService, str]) -> None:
    service, _ = seeded

    with pytest.raises(NoStrategyEvidenceError, match="No path is supported yet"):
        service.propose_strategy()


def test_propose_strategy_names_the_segments_it_used(seeded: tuple[ODIService, str]) -> None:
    service, _ = seeded
    segment = service.segment_market()[0]

    strategy = service.propose_strategy(segment_ids=[segment.id])

    assert strategy.segment_id == segment.id


def test_an_unknown_segment_id_is_an_error_not_a_smaller_scope(
    seeded: tuple[ODIService, str],
) -> None:
    service, _ = seeded
    service.segment_market()

    with pytest.raises(SegmentNotFoundError):
        service.propose_strategy(segment_ids=["ghost"])


def test_a_strategy_without_its_rejections_is_refused(seeded: tuple[ODIService, str]) -> None:
    service, _ = seeded
    service.segment_market()
    strategy = service.propose_strategy()
    bare = strategy.model_copy(update={"rejected": []})

    with pytest.raises(ValidationError, match="not a recommendation"):
        service.save_strategy(bare)


def test_the_unclustered_bucket_is_reported(seeded: tuple[ODIService, str]) -> None:
    service, _ = seeded
    lone = service.add_outcome(
        service.get_jobs()[0].id,
        statement="Minimize the number of outages when verifying the value",
        importance=7,
        satisfaction=2,
    )

    service.segment_market()
    unclustered = [outcome.id for outcome in service.unclustered_outcomes()]

    assert lone.id in unclustered
    clustered = service.list_segments()[0].outcome_ids
    assert not set(clustered) & set(unclustered)


def test_segments_and_strategy_reach_the_signals_feed(seeded: tuple[ODIService, str]) -> None:
    service, _ = seeded
    service.segment_market()
    service.propose_strategy()

    kinds = {signal.kind.value for signal in service.repo.signals.values()}

    assert {"segment_identified", "strategy_proposed"} <= kinds
    underserved = next(
        signal
        for signal in service.repo.signals.values()
        if signal.kind.value == "segment_identified"
    )
    assert underserved.severity == "notice"
