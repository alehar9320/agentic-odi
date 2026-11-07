"""Tests for Stage 6: the innovation strategy the segments imply."""

from __future__ import annotations

from agentic_odi_core import (
    Job,
    Outcome,
    Segment,
    SegmentVerdict,
    StrategyKind,
    compute_opportunity_score,
)
from agentic_odi_core.strategy import propose_strategy

_JOB_ID = "job-1"


def _outcome(
    statement: str,
    importance: float,
    satisfaction: float,
    outcome_id: str,
    job_id: str = _JOB_ID,
) -> Outcome:
    return Outcome(
        id=outcome_id,
        job_id=job_id,
        statement=statement,
        importance=importance,
        satisfaction=satisfaction,
        opportunity_score=compute_opportunity_score(importance, satisfaction),
    )


def _segment(
    verdict: SegmentVerdict | None,
    outcome_ids: list[str],
    segment_id: str = "seg-1",
    job_id: str = _JOB_ID,
) -> Segment:
    return Segment(
        id=segment_id,
        job_id=job_id,
        name=f"Platform engineers, cluster {segment_id}",
        people="Platform engineers",
        job_statement="Rotate a leaked secret without an outage",
        outcome_ids=outcome_ids,
        verdict=verdict,
        rationale="2 outcomes on the gather step.",
        confidence=0.75,
    )


def _job(job_id: str = _JOB_ID) -> Job:
    return Job(id=job_id, name="Rotate a leaked secret")


_GAP = _outcome("Minimize the time to rotate the secret", 9, 2, "gap")
_SERVED = _outcome("Minimize the time to verify the new value", 5, 5, "served")


def test_an_underserved_segment_on_a_served_job_is_a_differentiated_bet() -> None:
    segment = _segment(SegmentVerdict.UNDERSERVED, ["gap"])

    strategy = propose_strategy([segment], [_job()], [_GAP, _SERVED])

    assert strategy is not None
    assert strategy.kind is StrategyKind.DIFFERENTIATED
    assert strategy.segment_id == "seg-1"
    assert any("gap" in bet for bet in strategy.bets)
    assert "underserved" in strategy.thesis


def test_an_overserved_segment_is_a_disruptive_bet() -> None:
    cheap_a = _outcome("Minimize the number of clicks to rotate", 3, 9, "a")
    cheap_b = _outcome("Minimize the time to produce a report", 4, 8, "b")
    segment = _segment(SegmentVerdict.OVERSERVED, ["a", "b"])

    strategy = propose_strategy([segment], [_job()], [cheap_a, cheap_b])

    assert strategy is not None
    assert strategy.kind is StrategyKind.DISRUPTIVE
    assert "not asking for more" in strategy.thesis


def test_a_full_service_purchase_weakens_the_disruptive_bet_instead_of_hiding_it() -> None:
    heavy = _outcome("Minimize the time to rotate the secret", 9, 1, "a")
    light = _outcome("Minimize the number of clicks to rotate", 3, 9, "b")
    segment = _segment(SegmentVerdict.OVERSERVED, ["a", "b"])

    strategy = propose_strategy([segment], [_job()], [heavy, light])

    assert strategy is not None
    assert "full-service purchase" in strategy.thesis
    assert "weakens the case" in strategy.thesis


def test_outcomes_with_no_job_are_a_new_market_bet() -> None:
    orphan = _outcome(
        "Minimize the time to answer a security questionnaire", 9, 2, "orphan", job_id="gone"
    )
    strategy = propose_strategy([], [_job()], [orphan, _GAP, _SERVED])

    assert strategy is not None
    assert strategy.kind is StrategyKind.NEW_MARKET
    assert strategy.segment_id is None
    assert "no job in the store" in strategy.thesis


def test_a_differentiated_bet_beats_a_new_market_bet() -> None:
    """The paths are tried in evidence order: an existing job first."""
    segment = _segment(SegmentVerdict.UNDERSERVED, ["gap"])
    orphan = _outcome("Minimize the time to answer a questionnaire", 9, 2, "orphan", job_id="gone")

    strategy = propose_strategy([segment], [_job()], [_GAP, _SERVED, orphan])

    assert strategy is not None
    assert strategy.kind is StrategyKind.DIFFERENTIATED


def test_rejected_carries_one_reason_per_path_not_chosen() -> None:
    segment = _segment(SegmentVerdict.UNDERSERVED, ["gap"])

    strategy = propose_strategy([segment], [_job()], [_GAP, _SERVED])

    assert strategy is not None
    assert {entry["kind"] for entry in strategy.rejected} == {"disruptive", "new_market"}
    assert all(entry["why"] for entry in strategy.rejected)
    assert strategy.kind.value not in {entry["kind"] for entry in strategy.rejected}


def test_a_new_market_rejection_says_why_when_nothing_is_orphaned() -> None:
    segment = _segment(SegmentVerdict.UNDERSERVED, ["gap"])

    strategy = propose_strategy([segment], [_job()], [_GAP, _SERVED])

    assert strategy is not None
    rejection = next(entry for entry in strategy.rejected if entry["kind"] == "new_market")
    assert "already in the store" in rejection["why"]


def test_nothing_is_recommended_when_no_path_has_evidence() -> None:
    appropriately = _outcome("Minimize the time to rotate the secret", 6, 4, "a")
    segment = _segment(SegmentVerdict.APPROPRIATELY_SERVED, ["a"])

    assert propose_strategy([segment], [_job()], [appropriately]) is None
    assert propose_strategy([], [], []) is None


def test_the_strategy_id_is_stable_for_the_same_bet() -> None:
    segment = _segment(SegmentVerdict.UNDERSERVED, ["gap"])

    first = propose_strategy([segment], [_job()], [_GAP, _SERVED])
    second = propose_strategy([segment], [_job()], [_GAP, _SERVED])

    assert first is not None and second is not None
    assert first.id == second.id
