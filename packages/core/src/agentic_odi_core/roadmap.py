"""Derive the outcome roadmap from the decision log.

The roadmap is a **view**, not a store. ``build_roadmap`` groups the outcomes a
recorded decision chose by the quarter of that decision's date, so every row can
be traced back to the decision that put it there.

Pure and deterministic: no repository access, no provider call, no writes. Every
numeral is either a supplied measurement or a supplied timestamp; a measurement
nobody supplied renders ``not measured``, never ``0``.

Readiness choices pinned here (see ALH-38 and its test module):

* ``decided-but-unmoved`` — an outcome is on the roadmap when a **live** decision
  chose it and no movement has been measured yet. No measurement source exists
  on ``main`` yet (``E1``/``ALH-46`` owns stored baselines; ``B6``/``ALH-29``
  owns score history), so ``baseline``/``target`` are **supplied** through
  explicit maps and are ``None`` when nobody supplied them. The live outcome
  score is never read as a baseline: ``ALH-46`` requires a baseline to be
  captured at creation so it cannot drift.
* ``horizon=4`` — the number of quarters the view spans, counting back from the
  quarter that contains ``today``. A decision older than the window is excluded
  and counted with its reason.
* Supersession — a superseded decision contributes no rows; its successor does.
* Repeated chosen outcomes — an outcome chosen by two live decisions appears once
  per decision, because deduplicating would silently drop a recorded choice.
* Quarter boundaries are computed in UTC from ``decided_at``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol, runtime_checkable

#: A measurement nobody supplied. Never rendered as ``0``.
NOT_MEASURED = "not measured"


@runtime_checkable
class DecisionRecord(Protocol):
    """The decision attributes the derivation reads, and nothing else."""

    id: str
    job_id: str
    chosen_outcome_ids: list[str]
    decided_at: str
    superseded_by: str | None


@runtime_checkable
class OutcomeRecord(Protocol):
    """The outcome attributes the derivation reads."""

    id: str
    job_id: str
    statement: str


@dataclass(frozen=True)
class RoadmapEntry:
    """One decided outcome, placed in the quarter its decision was made."""

    period: str
    outcome_id: str
    statement: str
    decision_id: str
    baseline: float | None = None
    target: float | None = None
    #: The recorded value estimate, supplied by the caller (W1/ALH-64). ``None``
    #: is unknown, never zero. It is carried so ``order_by="value"`` can sort on
    #: it without the renderer recomputing anything.
    value: float | None = None


@dataclass(frozen=True)
class Roadmap:
    """The derived view plus what it left out, and why.

    The exclusions travel with the entries so a renderer cannot show the rows
    without being able to show the count and the reason.
    """

    entries: tuple[RoadmapEntry, ...] = ()
    undecided_count: int = 0
    horizon_excluded_count: int = 0
    superseded_excluded_count: int = 0
    horizon: int = 4

    @property
    def is_empty(self) -> bool:
        return not self.entries

    def exclusion_note(self) -> str:
        """One line naming what was left out and why, or the all-clear.

        A roadmap that hides its exclusions is the version people stop trusting,
        so this never returns an empty string.
        """
        parts: list[str] = []
        if self.undecided_count:
            parts.append(
                f"{self.undecided_count} outcome(s) have no decision and were excluded "
                "(undecided, not unscheduled)"
            )
        if self.horizon_excluded_count:
            parts.append(
                f"{self.horizon_excluded_count} decision(s) fall outside the "
                f"{self.horizon}-quarter window and were excluded"
            )
        if self.superseded_excluded_count:
            parts.append(
                f"{self.superseded_excluded_count} decision(s) were superseded and were excluded"
            )
        if not parts:
            return "No outcomes were excluded."
        return "; ".join(parts) + "."


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _quarter_of(moment: datetime) -> tuple[int, int]:
    moment = _as_utc(moment)
    return moment.year, (moment.month - 1) // 3 + 1


def _quarter_index(year: int, quarter: int) -> int:
    return year * 4 + (quarter - 1)


def _period(year: int, quarter: int) -> str:
    return f"{year}-Q{quarter}"


def _parse_decided_at(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, treating a missing offset as UTC."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return _as_utc(datetime.fromisoformat(text))


def build_roadmap(
    job_id: str,
    decisions: Sequence[DecisionRecord],
    outcomes: Sequence[OutcomeRecord],
    *,
    horizon: int = 4,
    today: date | None = None,
    baselines: Mapping[tuple[str, str], float | None] | None = None,
    targets: Mapping[tuple[str, str], float | None] | None = None,
    values: Mapping[str, float | None] | None = None,
    order_by: str = "quarter",
) -> Roadmap:
    """Group the outcomes a live decision chose into quarterly roadmap rows.

    ``decisions`` and ``outcomes`` are supplied records (anything exposing the
    attributes named below), so the derivation stays a pure function and the
    caller owns the fetch. ``today`` is explicit so a test never depends on when
    it runs.

    ``order_by="value"`` is **opt-in** and never the default: ordering by worth
    changes the byte output, and existing callers must not see their roadmap
    silently reorder. An outcome with no estimate sorts last under ``value``
    (unknown, not zero) while keeping its quarter grouping.
    """
    if horizon < 1:
        raise ValueError("horizon must be at least 1 quarter")
    if order_by not in ("quarter", "value"):
        raise ValueError("order_by must be 'quarter' or 'value'")
    if today is None:
        today = datetime.now(timezone.utc).date()  # noqa: DTZ005 — explicit UTC

    statements = {outcome.id: outcome.statement for outcome in outcomes}
    job_outcome_ids = {outcome.id for outcome in outcomes if outcome.job_id == job_id}

    decided_outcome_ids: set[str] = set()
    for decision in decisions:
        if decision.job_id != job_id:
            continue
        decided_outcome_ids.update(decision.chosen_outcome_ids)
    undecided_count = len(job_outcome_ids - decided_outcome_ids)

    superseded_excluded = 0
    horizon_excluded = 0
    window_end = _quarter_index(*_quarter_of(datetime(today.year, today.month, today.day)))
    window_start = window_end - (horizon - 1)

    rows: list[tuple[int, str, str, RoadmapEntry]] = []
    for decision in decisions:
        if decision.job_id != job_id:
            continue
        if decision.superseded_by is not None:
            superseded_excluded += 1
            continue
        moment = _parse_decided_at(decision.decided_at)
        index = _quarter_index(*_quarter_of(moment))
        if not window_start <= index <= window_end:
            horizon_excluded += 1
            continue
        period = _period(*_quarter_of(moment))
        for outcome_id in decision.chosen_outcome_ids:
            if outcome_id not in job_outcome_ids:
                continue
            rows.append(
                (
                    index,
                    decision.id,
                    outcome_id,
                    RoadmapEntry(
                        period=period,
                        outcome_id=outcome_id,
                        statement=statements.get(outcome_id, outcome_id),
                        decision_id=decision.id,
                        baseline=(baselines or {}).get((decision.id, outcome_id)),
                        target=(targets or {}).get((decision.id, outcome_id)),
                        value=(values or {}).get(outcome_id),
                    ),
                )
            )

    if order_by == "value":
        # Grouping by quarter is preserved: reordering across quarters would
        # emit a period header twice and break the renderer's grouping. Within a
        # quarter, a sized outcome comes before an unsized one (unknown sorts
        # last, never as zero), then highest value first.
        def value_key(row: tuple[int, str, str, RoadmapEntry]) -> tuple[int, int, float, str, str]:
            value = row[3].value
            unsized = 1 if value is None else 0
            return (row[0], unsized, -(value or 0.0), row[1], row[2])

        rows.sort(key=value_key)
    else:
        rows.sort(key=lambda row: (row[0], row[1], row[2]))
    return Roadmap(
        entries=tuple(row[3] for row in rows),
        undecided_count=undecided_count,
        horizon_excluded_count=horizon_excluded,
        superseded_excluded_count=superseded_excluded,
        horizon=horizon,
    )


def _fmt_measurement(value: float | None) -> str:
    if value is None:
        return NOT_MEASURED
    return f"{value:g}"


def render_roadmap(roadmap: Roadmap) -> str:
    """Render the derived roadmap as markdown.

    Deterministic: the same derivation yields identical bytes. The renderer does
    not regroup, recompute a quarter, or fetch anything.
    """
    lines: list[str] = ["# Outcome roadmap", ""]
    if roadmap.is_empty:
        lines.append("_No decisions yet._")
        lines.append("")
        lines.append(roadmap.exclusion_note())
        lines.append("")
        return "\n".join(lines).rstrip("\n") + "\n"

    current_period: str | None = None
    for entry in roadmap.entries:
        if entry.period != current_period:
            current_period = entry.period
            lines.append(f"## {entry.period}")
            lines.append("")
        lines.append(f"- **{entry.statement}**")
        lines.append(
            f"  - Outcome: `{entry.outcome_id}` · Baseline: {_fmt_measurement(entry.baseline)}"
            f" · Target: {_fmt_measurement(entry.target)}"
        )
        lines.append(f"  - Decision: `{entry.decision_id}`")
    lines.append("")
    lines.append(roadmap.exclusion_note())
    lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
