from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

import pytest
from agentic_odi_core.briefing import (
    Briefing,
    BriefingItem,
    BriefingItemKind,
    RunChange,
    RunResult,
    build_briefing,
)

NOW = datetime(2026, 11, 10, 2, 0, tzinfo=timezone.utc)


def _change(kind: BriefingItemKind, text: str, record_id: str, record_kind: str) -> RunChange:
    return RunChange(kind=kind, text=text, record_id=record_id, record_kind=record_kind)


def test_three_changes_become_three_items_in_a_stable_order() -> None:
    changes = (
        _change("added", "A new quote mentions onboarding.", "ev-1", "evidence"),
        _change("changed", "O-12 rose to an opportunity score of 14.2.", "o-12", "outcome"),
        _change("failed", "The nightly schedule failed to reach the model.", "sw-3", "agent_work"),
    )

    briefing = build_briefing(RunResult(run_id="run-1", changes=changes, created_at=NOW))

    assert briefing.run_id == "run-1"
    assert briefing.created_at == NOW
    assert [item.kind for item in briefing.items] == ["added", "changed", "failed"]
    assert [item.record_id for item in briefing.items] == ["ev-1", "o-12", "sw-3"]
    assert briefing.has_items


def test_the_same_run_reads_the_same_way_every_time() -> None:
    changes = (
        _change("added", "First.", "a", "evidence"),
        _change("changed", "Second.", "b", "outcome"),
    )

    first = build_briefing(RunResult(run_id="run-1", changes=changes, created_at=NOW))
    second = build_briefing(RunResult(run_id="run-1", changes=changes, created_at=NOW))

    assert first.to_dict() == second.to_dict()


def test_an_empty_result_is_an_honest_empty_briefing() -> None:
    briefing = build_briefing(RunResult(run_id="run-2", created_at=NOW))

    assert briefing.items == ()
    assert not briefing.has_items
    assert briefing.to_dict() == {"run_id": "run-2", "created_at": NOW.isoformat(), "items": []}


def test_an_item_without_a_record_is_rejected() -> None:
    with pytest.raises(ValueError, match="record_id"):
        BriefingItem(kind="added", text="Something happened.", record_id="", record_kind="evidence")

    with pytest.raises(ValueError, match="record_kind"):
        BriefingItem(kind="added", text="Something happened.", record_id="ev-1", record_kind="")


def test_a_line_that_is_just_an_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="prose"):
        BriefingItem(kind="added", text="ev-1", record_id="ev-1", record_kind="evidence")


def test_an_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="kind"):
        BriefingItem(
            kind=cast(BriefingItemKind, "removed"),
            text="Something left.",
            record_id="x",
            record_kind="evidence",
        )


def test_a_briefing_needs_a_run() -> None:
    with pytest.raises(ValueError, match="run_id"):
        build_briefing(RunResult(run_id="  "))


def test_a_briefing_round_trips_through_its_dict() -> None:
    briefing = build_briefing(
        RunResult(
            run_id="run-9",
            changes=(_change("added", "A new quote.", "ev-9", "evidence"),),
            created_at=NOW,
        )
    )

    restored = Briefing.from_dict(briefing.to_dict())

    assert restored == briefing
    assert restored.items[0].record_kind == "evidence"
