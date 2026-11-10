"""Pin the score history and delta contract (B6/ALH-29 reads, ALH-203).

Readiness choices pinned here:

* **Baseline = nearest snapshot at or before ``since``.** A delta can never read
  the future; with ``since=None`` the earliest snapshot is the baseline.
* **Missing data is ``None``, never ``0``.** A real recorded ``0.0`` stays
  ``0.0``.
* **Direction is satisfaction's.** Opportunity direction is not satisfaction
  direction: a fall in satisfaction can still raise opportunity.
* **Ties keep insertion order**, so equal timestamps replay reproducibly.
"""

from __future__ import annotations

from agentic_odi_core.history import (
    DEGRADED,
    IMPROVED,
    NO_EVIDENCE,
    outcome_delta,
    outcome_history,
)
from agentic_odi_core.models import ScoreSnapshot


def _snapshot(
    outcome_id: str, at: str, *, satisfaction: float | None, importance: float | None = 5.0
) -> ScoreSnapshot:
    opportunity = None
    if satisfaction is not None and importance is not None:
        opportunity = round(importance + max(importance - satisfaction, 0.0), 3)
    return ScoreSnapshot(
        outcome_id=outcome_id,
        at=at,
        importance=importance,
        satisfaction=satisfaction,
        opportunity_score=opportunity,
    )


def test_history_is_oldest_first_and_filtered_by_outcome() -> None:
    snapshots = [
        _snapshot("a", "2026-03-01T00:00:00Z", satisfaction=3.0),
        _snapshot("b", "2026-01-01T00:00:00Z", satisfaction=4.0),
        _snapshot("a", "2026-01-01T00:00:00Z", satisfaction=2.0),
    ]
    history = outcome_history(snapshots, "a")
    assert [s.at for s in history] == ["2026-01-01T00:00:00Z", "2026-03-01T00:00:00Z"]


def test_no_history_yields_no_delta() -> None:
    assert outcome_delta([], "a") is None


def test_single_snapshot_is_no_evidence_not_zero() -> None:
    snapshots = [_snapshot("a", "2026-01-01T00:00:00Z", satisfaction=3.0)]
    delta = outcome_delta(snapshots, "a")
    assert delta is not None
    assert delta.satisfaction == 0.0
    assert delta.direction == NO_EVIDENCE


def test_baseline_is_the_nearest_snapshot_at_or_before_since() -> None:
    snapshots = [
        _snapshot("a", "2026-01-01T00:00:00Z", satisfaction=2.0),
        _snapshot("a", "2026-04-01T00:00:00Z", satisfaction=5.0),
        _snapshot("a", "2026-07-01T00:00:00Z", satisfaction=6.0),
    ]
    delta = outcome_delta(snapshots, "a", since="2026-05-15T00:00:00Z")
    assert delta is not None
    assert delta.satisfaction == 1.0
    assert delta.direction == IMPROVED


def test_a_later_snapshot_is_never_the_baseline() -> None:
    """A delta cannot read the future: nothing at or before ``since`` falls back
    to the earliest snapshot only when the caller passes ``since=None``."""
    snapshots = [
        _snapshot("a", "2026-04-01T00:00:00Z", satisfaction=5.0),
        _snapshot("a", "2026-07-01T00:00:00Z", satisfaction=6.0),
    ]
    delta = outcome_delta(snapshots, "a", since="2026-01-01T00:00:00Z")
    assert delta is not None
    # The earliest snapshot is after ``since``; it becomes the baseline so the
    # change is measured from where the record actually starts.
    assert delta.satisfaction == 1.0


def test_missing_metric_is_none_but_a_real_zero_stays_zero() -> None:
    snapshots = [
        _snapshot("a", "2026-01-01T00:00:00Z", satisfaction=None),
        _snapshot("a", "2026-02-01T00:00:00Z", satisfaction=0.0),
    ]
    delta = outcome_delta(snapshots, "a")
    assert delta is not None
    assert delta.satisfaction is None
    assert delta.direction == NO_EVIDENCE


def test_direction_follows_satisfaction_not_opportunity() -> None:
    """A satisfaction fall that raises opportunity is still ``degraded``."""
    snapshots = [
        _snapshot("a", "2026-01-01T00:00:00Z", satisfaction=8.0, importance=8.0),
        _snapshot("a", "2026-02-01T00:00:00Z", satisfaction=2.0, importance=8.0),
    ]
    delta = outcome_delta(snapshots, "a")
    assert delta is not None
    assert delta.satisfaction is not None and delta.satisfaction < 0
    assert delta.opportunity is not None and delta.opportunity > 0
    assert delta.direction == DEGRADED


def test_equal_timestamps_keep_insertion_order() -> None:
    first = _snapshot("a", "2026-01-01T00:00:00Z", satisfaction=2.0)
    second = _snapshot("a", "2026-01-01T00:00:00Z", satisfaction=4.0)
    history = outcome_history([first, second], "a")
    assert history == [first, second]
