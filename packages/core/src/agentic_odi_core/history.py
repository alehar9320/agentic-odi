"""Read score history and compute signed deltas (B6/ALH-29, reads: ALH-203).

Pure functions over a supplied snapshot list: no repository access, no clock, no
writes. ``outcome_delta`` is a subtraction, which is the whole point of keeping
history — "did it move?" stops being a memory test.

Readiness choices pinned here (ALH-203 owns the same policy; recorded in
``test_history.py``):

* **Baseline = nearest snapshot at or before ``since``.** The comparison point
  is never *after* the reference moment, so a delta cannot read the future.
  When ``since`` is ``None`` the earliest snapshot is the baseline.
* **Missing data is ``no_evidence``, never ``0``.** A delta is ``None`` for a
  metric when either endpoint lacks that metric. A real recorded ``0.0`` stays
  ``0.0``.
* **Direction is per metric and the primary direction is satisfaction's.**
  Opportunity-score direction is not satisfaction direction: a rise in
  opportunity can come from a fall in satisfaction. The customer-facing metric
  (satisfaction) decides ``direction``; the components travel alongside so a
  caller can disagree without recomputing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

#: A metric nobody measured. Never rendered as ``0``.
NOT_MEASURED = "not measured"

IMPROVED = "improved"
DEGRADED = "degraded"
NO_EVIDENCE = "no_evidence"


@runtime_checkable
class SnapshotRecord(Protocol):
    """The snapshot attributes the reads use, and nothing else."""

    outcome_id: str
    at: str
    importance: float | None
    satisfaction: float | None
    opportunity_score: float | None


@dataclass(frozen=True)
class Delta:
    """A signed change between two snapshots, per metric.

    Each component is ``None`` when either endpoint lacks the metric, so a
    missing measurement never reads as ``0``. ``direction`` is satisfaction's
    direction, because that is the customer-facing metric a bet targets.
    """

    importance: float | None
    satisfaction: float | None
    opportunity: float | None
    direction: str


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_at(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, treating a missing offset as UTC."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return _as_utc(datetime.fromisoformat(text))


def _ordered(snapshots: Sequence[SnapshotRecord]) -> list[SnapshotRecord]:
    """Oldest first. A stable tie-break keeps equal timestamps reproducible."""
    return sorted(snapshots, key=lambda s: parse_at(s.at))


def outcome_history(snapshots: Sequence[SnapshotRecord], outcome_id: str) -> list[SnapshotRecord]:
    """Every snapshot for one outcome, oldest first."""
    return _ordered([s for s in snapshots if s.outcome_id == outcome_id])


def _delta_of(baseline: float | None, latest: float | None) -> float | None:
    if baseline is None or latest is None:
        return None
    return latest - baseline


def _direction_of(change: float | None) -> str:
    if change is None or change == 0:
        return NO_EVIDENCE
    return IMPROVED if change > 0 else DEGRADED


def outcome_delta(
    snapshots: Sequence[SnapshotRecord],
    outcome_id: str,
    *,
    since: str | None = None,
) -> Delta | None:
    """The signed change for one outcome, or ``None`` when there is no history.

    The baseline is the nearest snapshot at or before ``since`` (or the earliest
    snapshot when ``since`` is ``None``); the latest snapshot is the other end.
    """
    history = outcome_history(snapshots, outcome_id)
    if not history:
        return None
    latest = history[-1]
    if since is None:
        baseline = history[0]
    else:
        reference = parse_at(since)
        candidates = [s for s in history if parse_at(s.at) <= reference]
        baseline = candidates[-1] if candidates else history[0]
    satisfaction_change = _delta_of(baseline.satisfaction, latest.satisfaction)
    return Delta(
        importance=_delta_of(baseline.importance, latest.importance),
        satisfaction=satisfaction_change,
        opportunity=_delta_of(baseline.opportunity_score, latest.opportunity_score),
        direction=_direction_of(satisfaction_change),
    )
