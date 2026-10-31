"""Pin the roadmap derivation (C7, ALH-38) and its markdown render (C7.2).

Readiness choices pinned here, per ALH-38:

* ``decided-but-unmoved``: an outcome is on the roadmap when a **live** decision
  chose it. No movement store exists on ``main`` (``E1``/``ALH-46`` owns stored
  baselines, ``B6``/``ALH-29`` owns score history), so ``baseline``/``target``
  are supplied through explicit maps and stay ``None`` when nobody supplied
  them. The live outcome score is never read as a baseline.
* ``horizon=4``: the number of quarters the view spans, counting back from the
  quarter that contains the explicit ``today``. Older decisions are excluded and
  counted with a reason.
* Supersession: a superseded decision contributes no rows; its successor does.
* Repeated chosen outcomes: one row per decision, because deduplicating would
  silently drop a recorded choice.
* Quarter boundaries are computed in UTC from ``decided_at``.
* ``today`` is explicit so these tests are clock-independent.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
from agentic_odi_core.models import Decision, Outcome
from agentic_odi_core.roadmap import (
    NOT_MEASURED,
    RoadmapEntry,
    build_roadmap,
    render_roadmap,
)

GOLDEN = Path(__file__).parent / "golden" / "roadmap_fixture_job.md"

TODAY = date(2026, 11, 15)


def _outcome(outcome_id: str, statement: str, job_id: str = "job-1") -> Outcome:
    return Outcome(
        id=outcome_id,
        job_id=job_id,
        statement=statement,
        importance=8.0,
        satisfaction=3.0,
    )


def _decision(
    decision_id: str,
    chosen: list[str],
    decided_at: str,
    *,
    job_id: str = "job-1",
    superseded_by: str | None = None,
) -> Decision:
    return Decision(
        id=decision_id,
        job_id=job_id,
        chosen_outcome_ids=chosen,
        rationale="Recorded.",
        decided_by="alex",
        decided_at=decided_at,
        superseded_by=superseded_by,
    )


def _fixture() -> tuple[list[Decision], list[Outcome]]:
    outcomes = [
        _outcome("out-1", "Minimize the time it takes to publish a plugin"),
        _outcome("out-2", "Minimize the likelihood of a failed install when a customer upgrades"),
        _outcome("out-3", "Minimize the cost of supporting a new plugin when it ships"),
        _outcome("out-4", "Minimize the time it takes to document a plugin when it is released"),
    ]
    decisions = [
        _decision("dec-1", ["out-1"], "2026-10-01T00:00:00Z"),
        _decision("dec-2", ["out-2"], "2026-10-02T00:00:00Z"),
        _decision("dec-3", ["out-3"], "2026-11-01T00:00:00Z"),
    ]
    return decisions, outcomes


def test_three_decisions_produce_three_entries_in_date_order():
    decisions, outcomes = _fixture()
    roadmap = build_roadmap("job-1", decisions, outcomes, today=TODAY)
    assert [entry.decision_id for entry in roadmap.entries] == ["dec-1", "dec-2", "dec-3"]
    assert [entry.outcome_id for entry in roadmap.entries] == ["out-1", "out-2", "out-3"]


def test_undecided_outcome_is_excluded_and_counted():
    decisions, outcomes = _fixture()
    roadmap = build_roadmap("job-1", decisions, outcomes, today=TODAY)
    assert all(entry.outcome_id != "out-4" for entry in roadmap.entries)
    assert roadmap.undecided_count == 1
    assert "out-4" not in {entry.outcome_id for entry in roadmap.entries}
    assert "1 outcome(s) have no decision" in roadmap.exclusion_note()
    assert "not unscheduled" in roadmap.exclusion_note()


def test_quarters_come_from_the_decision_date_in_utc():
    decisions, outcomes = _fixture()
    roadmap = build_roadmap("job-1", decisions, outcomes, today=TODAY)
    assert roadmap.entries[0].period == "2026-Q4"
    assert roadmap.entries[2].period == "2026-Q4"

    # A quarter-boundary instant near midnight UTC lands in the new quarter.
    boundary = [_decision("dec-b", ["out-1"], "2026-10-01T00:00:00+00:00")]
    assert build_roadmap("job-1", boundary, outcomes, today=TODAY).entries[0].period == "2026-Q4"

    # 2026-09-30T23:59:59Z is still Q3.
    just_before = [_decision("dec-c", ["out-1"], "2026-09-30T23:59:59Z")]
    assert build_roadmap("job-1", just_before, outcomes, today=TODAY).entries[0].period == "2026-Q3"


def test_same_date_decisions_are_ordered_by_id():
    outcomes = [_outcome("out-1", "Minimize the time it takes to publish a plugin")]
    decisions = [
        _decision("dec-b", ["out-1"], "2026-10-01T00:00:00Z"),
        _decision("dec-a", ["out-1"], "2026-10-01T00:00:00Z"),
    ]
    roadmap = build_roadmap("job-1", decisions, outcomes, today=TODAY)
    assert [entry.decision_id for entry in roadmap.entries] == ["dec-a", "dec-b"]


def test_superseded_decision_is_excluded_and_counted():
    outcomes = [_outcome("out-1", "Minimize the time it takes to publish a plugin")]
    decisions = [
        _decision("dec-1", ["out-1"], "2026-10-01T00:00:00Z", superseded_by="dec-2"),
        _decision("dec-2", ["out-1"], "2026-10-02T00:00:00Z"),
    ]
    roadmap = build_roadmap("job-1", decisions, outcomes, today=TODAY)
    assert [entry.decision_id for entry in roadmap.entries] == ["dec-2"]
    assert roadmap.superseded_excluded_count == 1
    assert "superseded" in roadmap.exclusion_note()


def test_repeated_chosen_outcome_appears_once_per_decision():
    outcomes = [_outcome("out-1", "Minimize the time it takes to publish a plugin")]
    decisions = [
        _decision("dec-1", ["out-1"], "2026-10-01T00:00:00Z"),
        _decision("dec-2", ["out-1"], "2026-10-02T00:00:00Z"),
    ]
    roadmap = build_roadmap("job-1", decisions, outcomes, today=TODAY)
    assert [entry.decision_id for entry in roadmap.entries] == ["dec-1", "dec-2"]
    assert roadmap.undecided_count == 0


def test_missing_baseline_and_target_are_not_measured_never_zero():
    decisions, outcomes = _fixture()
    roadmap = build_roadmap("job-1", decisions, outcomes, today=TODAY)
    entry = roadmap.entries[0]
    assert entry.baseline is None and entry.target is None
    assert NOT_MEASURED in render_roadmap(roadmap)
    assert "Baseline: 0" not in render_roadmap(roadmap)


def test_supplied_baseline_and_target_are_interpolated():
    decisions, outcomes = _fixture()
    roadmap = build_roadmap(
        "job-1",
        decisions,
        outcomes,
        today=TODAY,
        baselines={("dec-1", "out-1"): 3.0},
        targets={("dec-1", "out-1"): 7.5},
    )
    assert roadmap.entries[0].baseline == 3.0
    assert roadmap.entries[0].target == 7.5
    text = render_roadmap(roadmap)
    assert "Baseline: 3" in text
    assert "Target: 7.5" in text


def test_horizon_excludes_older_decisions_and_counts_them():
    outcomes = [_outcome("out-1", "Minimize the time it takes to publish a plugin")]
    decisions = [
        _decision("dec-old", ["out-1"], "2024-01-01T00:00:00Z"),
        _decision("dec-new", ["out-1"], "2026-11-01T00:00:00Z"),
    ]
    roadmap = build_roadmap("job-1", decisions, outcomes, horizon=4, today=TODAY)
    assert [entry.decision_id for entry in roadmap.entries] == ["dec-new"]
    assert roadmap.horizon_excluded_count == 1
    assert "4-quarter window" in roadmap.exclusion_note()


def test_horizon_one_keeps_only_the_current_quarter():
    outcomes = [_outcome("out-1", "Minimize the time it takes to publish a plugin")]
    decisions = [
        _decision("dec-q3", ["out-1"], "2026-09-01T00:00:00Z"),
        _decision("dec-q4", ["out-1"], "2026-11-01T00:00:00Z"),
    ]
    roadmap = build_roadmap("job-1", decisions, outcomes, horizon=1, today=TODAY)
    assert [entry.decision_id for entry in roadmap.entries] == ["dec-q4"]


def test_horizon_must_be_positive():
    import pytest

    with pytest.raises(ValueError):
        build_roadmap("job-1", [], [], horizon=0, today=TODAY)


def test_empty_decision_set_is_the_one_line_no_decisions_yet():
    outcomes = [_outcome("out-1", "Minimize the time it takes to publish a plugin")]
    roadmap = build_roadmap("job-1", [], outcomes, today=TODAY)
    assert roadmap.is_empty
    text = render_roadmap(roadmap)
    assert "_No decisions yet._" in text
    assert "1 outcome(s) have no decision" in text


def test_decisions_from_another_job_are_ignored():
    outcomes = [_outcome("out-1", "Minimize the time it takes to publish a plugin")]
    decisions = [_decision("dec-x", ["out-1"], "2026-11-01T00:00:00Z", job_id="other-job")]
    roadmap = build_roadmap("job-1", decisions, outcomes, today=TODAY)
    assert roadmap.is_empty
    assert roadmap.undecided_count == 1


def test_chosen_outcome_from_another_job_is_not_a_row():
    outcomes = [
        _outcome("out-1", "Minimize the time it takes to publish a plugin"),
        _outcome("out-9", "Minimize the cost of supporting a plugin", job_id="other-job"),
    ]
    decisions = [_decision("dec-1", ["out-1", "out-9"], "2026-11-01T00:00:00Z")]
    roadmap = build_roadmap("job-1", decisions, outcomes, today=TODAY)
    assert [entry.outcome_id for entry in roadmap.entries] == ["out-1"]


def test_render_is_deterministic():
    decisions, outcomes = _fixture()
    first = render_roadmap(build_roadmap("job-1", decisions, outcomes, today=TODAY))
    second = render_roadmap(build_roadmap("job-1", decisions, outcomes, today=TODAY))
    assert first == second


def test_every_numeral_in_the_render_exists_in_the_derivation():
    decisions, outcomes = _fixture()
    roadmap = build_roadmap(
        "job-1",
        decisions,
        outcomes,
        today=TODAY,
        baselines={("dec-1", "out-1"): 3.0},
        targets={("dec-1", "out-1"): 7.5},
    )
    text = render_roadmap(roadmap)
    allowed: set[str] = set()
    for entry in roadmap.entries:
        allowed |= set(re.findall(r"\d+(?:\.\d+)?", entry.period))
        allowed |= set(re.findall(r"\d+(?:\.\d+)?", entry.statement))
        allowed |= set(re.findall(r"\d+(?:\.\d+)?", entry.outcome_id))
        allowed |= set(re.findall(r"\d+(?:\.\d+)?", entry.decision_id))
        if entry.baseline is not None:
            allowed.add(f"{entry.baseline:g}")
        if entry.target is not None:
            allowed.add(f"{entry.target:g}")
    allowed.add(str(roadmap.undecided_count))
    allowed.add(str(roadmap.horizon_excluded_count))
    allowed.add(str(roadmap.superseded_excluded_count))
    allowed.add(str(roadmap.horizon))
    for numeral in re.findall(r"\d+(?:\.\d+)?", text):
        assert numeral in allowed, f"fabricated numeral {numeral!r} in roadmap"


def test_golden_derivation_matches_exactly():
    decisions, outcomes = _fixture()
    roadmap = build_roadmap(
        "job-1",
        decisions,
        outcomes,
        today=TODAY,
        baselines={("dec-1", "out-1"): 3.0},
        targets={("dec-1", "out-1"): 7.5},
    )
    assert render_roadmap(roadmap) == GOLDEN.read_text(encoding="utf-8")


def test_roadmap_entry_is_frozen_and_carries_the_decision_id():
    entry = RoadmapEntry(period="2026-Q4", outcome_id="out-1", statement="s", decision_id="dec-1")
    assert entry.decision_id == "dec-1"
    try:
        entry.period = "2026-Q1"  # type: ignore[misc]
    except Exception as exc:  # noqa: BLE001
        assert isinstance(exc, Exception)
    else:
        raise AssertionError("RoadmapEntry must be frozen")


# --------------------------------------------------- W1 value ordering (ALH-64)


def test_value_order_is_opt_in_and_the_default_is_unchanged():
    decisions, outcomes = _fixture()
    default = build_roadmap("job-1", decisions, outcomes, today=TODAY)
    explicit = build_roadmap("job-1", decisions, outcomes, today=TODAY, order_by="quarter")
    assert [e.outcome_id for e in default.entries] == [e.outcome_id for e in explicit.entries]
    assert [e.outcome_id for e in default.entries] == ["out-1", "out-2", "out-3"]


def test_value_order_ranks_within_a_quarter_and_keeps_the_grouping():
    decisions, outcomes = _fixture()
    # All three decisions are in 2026-Q4, so value ordering reorders within it.
    roadmap = build_roadmap(
        "job-1",
        decisions,
        outcomes,
        today=TODAY,
        values={"out-1": 100.0, "out-2": 900.0, "out-3": 400.0},
        order_by="value",
    )
    assert [e.outcome_id for e in roadmap.entries] == ["out-2", "out-3", "out-1"]
    # The quarter grouping is intact: one period for the whole view.
    assert {e.period for e in roadmap.entries} == {"2026-Q4"}


def test_an_unsized_outcome_sorts_last_never_as_zero():
    decisions, outcomes = _fixture()
    roadmap = build_roadmap(
        "job-1",
        decisions,
        outcomes,
        today=TODAY,
        # out-2 has no value; a zero would put it last anyway, so give out-1 and
        # out-3 values below and above the implicit zero to prove the ordering.
        values={"out-1": -0.0, "out-3": 0.0},
        order_by="value",
    )
    assert [e.outcome_id for e in roadmap.entries] == ["out-1", "out-3", "out-2"]
    assert roadmap.entries[-1].value is None


def test_value_ordering_does_not_cross_quarter_boundaries():
    outcomes = [_outcome("out-1", "Minimize the time it takes to publish a plugin")]
    decisions = [
        _decision("dec-1", ["out-1"], "2026-10-01T00:00:00Z"),
        _decision("dec-2", ["out-1"], "2026-11-01T00:00:00Z"),
    ]
    roadmap = build_roadmap(
        "job-1",
        decisions,
        outcomes,
        today=TODAY,
        values={"out-1": 5.0},
        order_by="value",
    )
    # Both rows are the same outcome; the period never regresses.
    assert [e.period for e in roadmap.entries] == ["2026-Q4", "2026-Q4"]


def test_an_unknown_order_by_is_refused():
    decisions, outcomes = _fixture()
    with pytest.raises(ValueError, match="order_by must be"):
        build_roadmap("job-1", decisions, outcomes, today=TODAY, order_by="worth")
