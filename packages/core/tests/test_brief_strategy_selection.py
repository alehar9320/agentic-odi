"""The brief shows the one strategy the decision is about, and says nothing otherwise.

``select_brief_strategy`` is pure: it reads the segments and the strategy
records it is handed and picks the latest one whose segment overlaps the
decision's chosen outcomes. With no overlap there is no strategy to show, and
the brief must omit the section rather than borrow one from another segment.
"""

from __future__ import annotations

from agentic_odi_core.brief import (
    BriefSegment,
    BriefStrategyRecord,
    select_brief_strategy,
)


def _record(strategy_id: str, segment_id: str, chosen_at: str) -> BriefStrategyRecord:
    return BriefStrategyRecord(
        strategy_id=strategy_id,
        segment_id=segment_id,
        chosen_at=chosen_at,
        kind="differentiated",
        rationale=f"Why {strategy_id}.",
        expected_effect=f"Effect of {strategy_id}.",
    )


def test_the_latest_strategy_on_the_overlapping_segment_wins() -> None:
    segments = [
        BriefSegment(segment_id="seg-1", name="Platform engineers", outcome_ids=("out-1", "out-2")),
        BriefSegment(segment_id="seg-2", name="On-call engineers", outcome_ids=("out-3",)),
    ]
    strategies = [
        _record("strategy-old", "seg-1", "2026-10-01T09:00:00+00:00"),
        _record("strategy-new", "seg-1", "2026-11-01T09:00:00+00:00"),
        _record("strategy-other", "seg-2", "2026-11-05T09:00:00+00:00"),
    ]

    selected = select_brief_strategy(["out-1"], segments, strategies)

    assert selected is not None
    assert selected.kind == "differentiated"
    assert selected.rationale == "Why strategy-new."
    assert selected.segment_name == "Platform engineers"


def test_across_overlapping_segments_the_latest_candidate_wins() -> None:
    segments = [
        BriefSegment(segment_id="seg-1", name="Platform engineers", outcome_ids=("out-1",)),
        BriefSegment(segment_id="seg-2", name="On-call engineers", outcome_ids=("out-1", "out-2")),
    ]
    strategies = [
        _record("strategy-first", "seg-1", "2026-10-01T09:00:00+00:00"),
        _record("strategy-second", "seg-2", "2026-10-15T09:00:00+00:00"),
    ]

    selected = select_brief_strategy(["out-1"], segments, strategies)

    assert selected is not None
    assert selected.segment_name == "On-call engineers"
    assert selected.rationale == "Why strategy-second."


def test_same_timestamp_breaks_the_tie_by_strategy_id() -> None:
    segments = [BriefSegment(segment_id="seg-1", name="Platform engineers", outcome_ids=("out-1",))]
    strategies = [
        _record("strategy-a", "seg-1", "2026-11-01T09:00:00+00:00"),
        _record("strategy-b", "seg-1", "2026-11-01T09:00:00+00:00"),
    ]

    selected = select_brief_strategy(["out-1"], segments, strategies)

    assert selected is not None
    assert selected.rationale == "Why strategy-b."


def test_no_overlapping_segment_means_no_strategy() -> None:
    segments = [BriefSegment(segment_id="seg-1", name="Platform engineers", outcome_ids=("out-1",))]
    strategies = [_record("strategy-1", "seg-1", "2026-11-01T09:00:00+00:00")]

    assert select_brief_strategy(["out-9"], segments, strategies) is None
    assert select_brief_strategy(["out-1"], segments, []) is None
    assert select_brief_strategy(["out-1"], [], strategies) is None
