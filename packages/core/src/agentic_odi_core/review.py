"""Review a past decision against today's numbers (C8/ALH-39).

Pure and clock-explicit: the derivation takes supplied snapshots, decisions, and
outcomes, plus an explicit ``today``. It never reads the store, fetches, or
writes. A review that needs data from outside the supplied records is not a
review.

Readiness choices pinned here (recorded in ``test_review.py``):

* **Five states, not three.** Each chosen outcome is ``improved``, ``degraded``,
  ``no_evidence``, ``no change``, or ``orphaned``. The description first declared
  three but the acceptance criteria require the literal ``no change`` and
  ``orphaned``, so all five exist rather than dropping a required state.
* **Direction is satisfaction's.** A rise in the opportunity score is not a
  satisfaction rise, so ``improved``/``degraded`` follow satisfaction. The
  components still travel so a caller can disagree.
* **Missing evidence is not zero movement.** No snapshot for a chosen outcome is
  ``no_evidence``, never ``no change`` and never ``degraded``.
* **An outcome that no longer exists is ``orphaned``**, reported rather than
  crashing the review.
* **Days elapsed is computed at read time** from ``decided_at`` against the
  supplied ``today`` (a date), so tests use a fixed clock.
* **A decision older than a quarter** means more than one calendar quarter has
  elapsed; the prompt offers the review on that basis.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol, runtime_checkable

from agentic_odi_core.history import (
    IMPROVED,
    NO_EVIDENCE,
    SnapshotRecord,
    parse_at,
)
from agentic_odi_core.history import (
    outcome_delta as _outcome_delta,
)


@runtime_checkable
class DecisionRecord(Protocol):
    """The decision attributes the review reads, and nothing else."""

    id: str
    job_id: str
    decided_at: str
    chosen_outcome_ids: list[str]


@runtime_checkable
class OutcomeRecord(Protocol):
    """The outcome attributes the review reads, and nothing else."""

    id: str
    statement: str


#: A chosen outcome whose record no longer exists.
ORPHANED = "orphaned"
#: A measured outcome whose satisfaction is unchanged.
NO_CHANGE = "no change"

REVIEW_STATES = (IMPROVED, "degraded", NO_EVIDENCE, NO_CHANGE, ORPHANED)


@dataclass(frozen=True)
class OutcomeReview:
    """One chosen outcome, compared against today's numbers."""

    outcome_id: str
    statement: str | None
    state: str
    satisfaction_change: float | None = None
    importance_change: float | None = None
    opportunity_change: float | None = None


@dataclass(frozen=True)
class DecisionReview:
    """A decision re-examined, with how long ago it was made."""

    decision_id: str
    job_id: str
    decided_at: str
    days_elapsed: int
    outcomes: tuple[OutcomeReview, ...] = ()

    @property
    def stale(self) -> bool:
        """Whether more than one calendar quarter has passed (the review offer)."""
        return self.days_elapsed > 91

    @property
    def moved_count(self) -> int:
        return sum(1 for o in self.outcomes if o.state in (IMPROVED, "degraded"))

    def summary(self) -> str:
        """One line naming what changed and what could not be measured."""
        if not self.outcomes:
            return "This decision chose no outcomes."
        parts: list[str] = []
        improved = sum(1 for o in self.outcomes if o.state == IMPROVED)
        degraded = sum(1 for o in self.outcomes if o.state == "degraded")
        no_change = sum(1 for o in self.outcomes if o.state == NO_CHANGE)
        no_evidence = sum(1 for o in self.outcomes if o.state == NO_EVIDENCE)
        orphaned = sum(1 for o in self.outcomes if o.state == ORPHANED)
        if improved:
            parts.append(f"{improved} improved")
        if degraded:
            parts.append(f"{degraded} degraded")
        if no_change:
            parts.append(f"{no_change} with no change")
        if no_evidence:
            parts.append(f"{no_evidence} with no evidence")
        if orphaned:
            parts.append(f"{orphaned} orphaned")
        return f"{self.days_elapsed} day(s) on: " + ", ".join(parts) + "."


def _days_between(decided_at: str, today: date) -> int:
    moment = parse_at(decided_at)
    end = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    return max(0, (end - moment).days)


def review_decision(
    decision: DecisionRecord,
    outcomes: Sequence[OutcomeRecord],
    snapshots: Sequence[SnapshotRecord],
    *,
    today: date,
) -> DecisionReview:
    """Compare a decision's chosen outcomes against the latest snapshots.

    ``decision`` and ``outcomes`` are supplied records; the caller owns the
    fetch. Each chosen outcome resolves to one of the five states, and a chosen
    outcome that no longer exists is ``orphaned`` rather than a crash.
    """
    job_id = decision.job_id
    decided_at = decision.decided_at
    decision_id = decision.id
    chosen = list(decision.chosen_outcome_ids)
    by_id = {o.id: o for o in outcomes}

    reviews: list[OutcomeReview] = []
    for outcome_id in chosen:
        record = by_id.get(outcome_id)
        if record is None:
            reviews.append(OutcomeReview(outcome_id=outcome_id, statement=None, state=ORPHANED))
            continue
        statement = record.statement
        # The comparison point is never after the decision: a snapshot taken
        # later cannot be the "then" side of "then vs now". With no snapshot at
        # or before the decision there is nothing to compare against, which is
        # no evidence, not zero movement.
        at_or_before = [
            s
            for s in snapshots
            if s.outcome_id == outcome_id and parse_at(s.at) <= parse_at(decided_at)
        ]
        if not at_or_before:
            reviews.append(
                OutcomeReview(outcome_id=outcome_id, statement=statement, state=NO_EVIDENCE)
            )
            continue
        delta = _outcome_delta(snapshots, outcome_id, since=decided_at)
        if delta is None or delta.satisfaction is None:
            reviews.append(
                OutcomeReview(outcome_id=outcome_id, statement=statement, state=NO_EVIDENCE)
            )
            continue
        if delta.satisfaction == 0:
            state = NO_CHANGE
        else:
            state = delta.direction
        reviews.append(
            OutcomeReview(
                outcome_id=outcome_id,
                statement=statement,
                state=state,
                satisfaction_change=delta.satisfaction,
                importance_change=delta.importance,
                opportunity_change=delta.opportunity,
            )
        )

    return DecisionReview(
        decision_id=decision_id,
        job_id=job_id,
        decided_at=decided_at,
        days_elapsed=_days_between(decided_at, today),
        outcomes=tuple(reviews),
    )


def _fmt(value: float | None) -> str:
    if value is None:
        return "not measured"
    return f"{value:+g}"


def render_review(review: DecisionReview) -> str:
    """Render a decision review as markdown, deterministically."""
    lines: list[str] = [f"# Decision review — `{review.decision_id}`", ""]
    lines.append(f"Decided {review.decided_at} ({review.days_elapsed} day(s) ago).")
    lines.append("")
    for outcome in review.outcomes:
        label = outcome.statement or outcome.outcome_id
        if outcome.state == ORPHANED:
            lines.append(f"- **{label}** — orphaned (the outcome no longer exists)")
            continue
        if outcome.state == NO_EVIDENCE:
            lines.append(f"- **{label}** — no evidence (no score recorded since the decision)")
            continue
        change = _fmt(outcome.satisfaction_change)
        lines.append(f"- **{label}** — {outcome.state} (satisfaction {change})")
    lines.append("")
    lines.append(review.summary())
    lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
