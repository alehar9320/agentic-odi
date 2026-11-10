"""Align two or three outcomes on shared axes so a choice is visible.

``align_outcomes`` is a **pure** function of its inputs, like
:func:`agentic_odi_core.brief.render_brief`: no repository access, no fetching,
no writes. It transposes the candidates — one row per metric, one cell per
outcome — because transposed data is what makes columns comparable; a list of
objects per outcome is not.

A metric nobody measured renders the literal :data:`NOT_MEASURED`, never a zero.
A real recorded ``0`` stays ``0``. The product never declares a winner: it shows
the axes, and a person decides.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from agentic_odi_core.brief import NOT_MEASURED
from agentic_odi_core.evaluation import classify_opportunity

#: Two bets is the smallest comparison; three is the most a person can hold in
#: mind at once. A fourth is refused rather than silently dropped.
MIN_COMPARE_OUTCOMES = 2
MAX_COMPARE_OUTCOMES = 3


@dataclass(frozen=True)
class CompareCandidate:
    """One outcome to compare, with every axis supplied by the caller.

    ``None`` means the measurement was not supplied and must render as such.
    """

    outcome_id: str
    statement: str
    score: float | None = None
    importance: float | None = None
    satisfaction: float | None = None
    stage: str | None = None
    evidence_count: int | None = None
    sample_size: int | None = None
    effort: str | None = None


@dataclass(frozen=True)
class CompareRow:
    """One metric across every column, cells in the candidates' given order."""

    metric: str
    label: str
    cells: tuple[str, ...]


@dataclass(frozen=True)
class OutcomeComparison:
    """Aligned rows over a fixed column order."""

    columns: tuple[str, ...]
    statements: tuple[str, ...]
    rows: tuple[CompareRow, ...]


def _fmt(value: float | None) -> str:
    """Render a number compactly, or the explicit missing marker."""
    if value is None:
        return NOT_MEASURED
    return f"{value:g}"


def _text(value: str | None) -> str:
    return value if value else NOT_MEASURED


def _count(value: int | None) -> str:
    return NOT_MEASURED if value is None else str(value)


def align_outcomes(candidates: Sequence[CompareCandidate]) -> OutcomeComparison:
    """Transpose candidates into rows, one cell per column.

    Every always-on axis is present even when no candidate measured it, so the
    absence is visible. ``effort`` is the exception: it is shown only when a
    candidate supplies it, because an effort row that can never be measured is
    noise, not information.
    """
    columns = tuple(candidate.outcome_id for candidate in candidates)
    statements = tuple(candidate.statement for candidate in candidates)

    rows: list[CompareRow] = [
        CompareRow("score", "Opportunity score", tuple(_fmt(c.score) for c in candidates)),
        CompareRow(
            "band",
            "Band",
            tuple(_text(classify_opportunity(c.score)) for c in candidates),
        ),
        CompareRow("importance", "Importance", tuple(_fmt(c.importance) for c in candidates)),
        CompareRow("satisfaction", "Satisfaction", tuple(_fmt(c.satisfaction) for c in candidates)),
        CompareRow("stage", "Stage", tuple(_text(c.stage) for c in candidates)),
        CompareRow(
            "evidence_count",
            "Evidence count",
            tuple(_count(c.evidence_count) for c in candidates),
        ),
        CompareRow("sample_size", "Sample size", tuple(_count(c.sample_size) for c in candidates)),
    ]

    if any(candidate.effort is not None for candidate in candidates):
        rows.append(CompareRow("effort", "Effort", tuple(_text(c.effort) for c in candidates)))

    return OutcomeComparison(columns=columns, statements=statements, rows=tuple(rows))
