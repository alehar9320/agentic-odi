"""Assemble the decision memo from what is already recorded (M3-11/ALH-97).

One page a product leader can sign: the decision, why now, the evidence with its
citations, the options we rejected and why, what the chosen outcome is worth,
how we will know it worked, and what we still do not know — every number copied
from a record, never derived.

Readiness choices pinned here (recorded in ``test_memo.py``):

* **Assembly is deterministic and reads nothing.** ``build_memo`` takes the
  records; it does not open a store, invoke a provider, or read a clock. "Why
  now" is derived from the decision's own ``decided_at``, so it is reproducible.
* **A missing section is omitted with a one-line reason**, the rule ``C1``
  established. *What it is worth* says "no value estimate recorded" and renders
  no zero; *How we will know* says which success-condition input is missing.
* **The memo is generated on read and never stored.** A stale stored memo would
  be worse than none, so there is no memo entity and no memo event.
* **An unknown decision raises**, so "no such decision" is never confused with
  an empty memo.
* **The framing sentence is not this increment's job.** ``M3-04`` narrates; the
  memo is the deterministic facts a narrator may later frame.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from agentic_odi_core.brief import NOT_MEASURED
from agentic_odi_core.errors import NotFoundError
from agentic_odi_core.evaluation import classify_opportunity, classify_value
from agentic_odi_core.models import Bet, Decision, Evidence, Outcome

#: The one-line reason a section is omitted, matching ``C1``'s rule: never
#: placeholder prose, never a zero.
NO_VALUE_NOTE = "_No value estimate recorded for the chosen outcome — worth is unknown, not zero._"
NO_CRITERIA_NOTE = "_No success criteria recorded — we have not said how we will know it worked._"
NO_HOLES_NOTE = "_No recorded holes — this is not proof that no risk remains._"


@runtime_checkable
class MemoCriterion(Protocol):
    """The success-criterion attributes the memo reads, and nothing else.

    Success criteria are a later enrichment (``M2-08``); until they have a model,
    the memo reads only the one attribute it needs so any record with a
    ``statement`` can supply them.
    """

    statement: str


@dataclass(frozen=True)
class MemoClaim:
    """A chosen outcome and the measurements the memo attributes to it.

    ``sources`` are the evidence records linked to *this* outcome, so a claim's
    citation travels with the claim instead of appearing in a detached list.
    """

    outcome_id: str
    statement: str | None
    score: float | None
    band: str | None
    n: int | None
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoRejection:
    """A rejected option: its statement when it still resolves, and the reason."""

    outcome_id: str
    statement: str | None
    reason: str


@dataclass(frozen=True)
class MemoBet:
    """The bet that answers "how we will know": its hypothesis, target and date."""

    hypothesis: str
    target: float
    measure_by: str


@dataclass(frozen=True)
class Memo:
    """The assembled memo. Every field is copied from a record, or is empty."""

    decision_id: str
    job_id: str
    decided_at: str
    decided_by: str
    rationale: str
    confidence: str
    superseded_by: str | None
    superseded_at: str | None
    why_now: str
    chosen: tuple[MemoClaim, ...] = ()
    rejected: tuple[MemoRejection, ...] = ()
    sources: tuple[str, ...] = ()
    value_outcome_id: str | None = None
    value_estimate: float | None = None
    value_unit: str | None = None
    value_basis: str = "estimate"
    value_n: int | None = None
    value_source: str | None = None
    criteria: tuple[str, ...] = ()
    bet: MemoBet | None = None
    holes: tuple[str, ...] = field(default_factory=tuple)


class MemoDecisionNotFoundError(NotFoundError):
    """The requested decision does not exist. Never confused with an empty memo.

    A :class:`NotFoundError` so the CLI, MCP and Studio all map it to a 404,
    rather than letting a lookup failure surface as a server error.
    """

    def __init__(self, decision_id: str) -> None:
        self.decision_id = decision_id
        super().__init__(decision_id, "Decision")


def _escape(text: str) -> str:
    """Escape HTML-significant characters in recorded text.

    A rationale, a statement or a source label is text, not markup: a
    ``<script>`` inside one must render as characters, not execute.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt(value: float | None) -> str:
    """Render a measurement compactly; ``None`` is ``not measured``, never ``0``."""
    if value is None:
        return NOT_MEASURED
    return f"{value:g}"


def _as_text(value: object) -> str:
    """Render an enum by its value, a string as itself, anything else as text."""
    return str(getattr(value, "value", value))


def _why_now(decided_at: str) -> str:
    """The "why now" line, derived from the decision's own timestamp.

    No clock is read: the sentence restates when the decision was made, which is
    a fact the record already carries. ``decided_at`` may be a date or a
    timestamp; the date part is what a reader needs.
    """
    day = decided_at.split("T", 1)[0].split(" ", 1)[0]
    return f"This decision was recorded on {day}."


def _claim(outcome: Outcome, sources: tuple[str, ...]) -> MemoClaim:
    counts = [
        count for count in (outcome.importance_n, outcome.satisfaction_n) if count is not None
    ]
    return MemoClaim(
        outcome_id=outcome.id,
        statement=outcome.statement or None,
        score=outcome.opportunity_score,
        band=classify_opportunity(outcome.opportunity_score),
        n=max(counts) if counts else None,
        sources=sources,
    )


def build_memo(
    decision: Decision,
    *,
    outcomes: Sequence[Outcome],
    evidence: Sequence[Evidence],
    criteria: Sequence[MemoCriterion] = (),
    bets: Sequence[Bet] = (),
    holes: Sequence[str] = (),
    chosen_outcome_id: str | None = None,
) -> Memo:
    """Assemble the memo from the records. No store, no clock, no model.

    ``chosen_outcome_id`` pins which chosen outcome the value and criteria
    sections describe; when omitted the decision's first chosen outcome is used.
    """
    by_id = {outcome.id: outcome for outcome in outcomes}
    per_outcome_sources: dict[str, list[str]] = {}
    job_sources: list[str] = []
    for record in evidence:
        if record.name not in job_sources:
            job_sources.append(record.name)
        if record.outcome_id is not None:
            linked = per_outcome_sources.setdefault(record.outcome_id, [])
            if record.name not in linked:
                linked.append(record.name)

    chosen_ids = [str(outcome_id) for outcome_id in decision.chosen_outcome_ids]
    chosen = tuple(
        _claim(by_id[outcome_id], tuple(per_outcome_sources.get(outcome_id, ())))
        if outcome_id in by_id
        else MemoClaim(outcome_id=outcome_id, statement=None, score=None, band="unscored", n=None)
        for outcome_id in chosen_ids
    )

    value_outcome_id = chosen_outcome_id or (chosen_ids[0] if chosen_ids else None)
    value_outcome = by_id.get(value_outcome_id) if value_outcome_id else None

    bet = None
    for bet_record in bets:
        if bet_record.outcome_id == value_outcome_id:
            bet = MemoBet(
                hypothesis=bet_record.hypothesis,
                target=float(bet_record.target),
                measure_by=bet_record.measure_by,
            )
            break

    return Memo(
        decision_id=decision.id,
        job_id=decision.job_id,
        decided_at=decision.decided_at,
        decided_by=decision.decided_by,
        rationale=decision.rationale,
        confidence=_as_text(decision.confidence),
        superseded_by=decision.superseded_by,
        superseded_at=decision.superseded_at,
        why_now=_why_now(decision.decided_at),
        chosen=chosen,
        rejected=tuple(
            MemoRejection(
                outcome_id=record.outcome_id,
                statement=by_id[record.outcome_id].statement
                if record.outcome_id in by_id
                else None,
                reason=record.reason,
            )
            for record in decision.rejected
        ),
        sources=tuple(job_sources),
        value_outcome_id=value_outcome_id if value_outcome is not None else None,
        value_estimate=value_outcome.value_estimate if value_outcome else None,
        value_unit=value_outcome.value_unit if value_outcome else None,
        value_basis=_as_text(value_outcome.value_basis) if value_outcome else "estimate",
        value_n=value_outcome.value_n if value_outcome else None,
        value_source=value_outcome.value_source if value_outcome else None,
        criteria=tuple(criterion.statement for criterion in criteria),
        bet=bet,
        holes=tuple(str(hole) for hole in holes),
    )


def _render_claims(memo: Memo) -> list[str]:
    """*What the evidence says* — a claim per chosen outcome, each citing its sources."""
    lines = ["## What the evidence says", ""]
    if not memo.chosen:
        lines.append("_No chosen outcome recorded — the decision names nothing to justify._")
        lines.append("")
        return lines
    for claim in memo.chosen:
        label = f" — {_escape(claim.statement)}" if claim.statement else ""
        if claim.score is None:
            lines.append(f"- `{claim.outcome_id}`{label}: score {NOT_MEASURED}")
        else:
            band = claim.band or NOT_MEASURED
            lines.append(
                f"- `{claim.outcome_id}`{label}: score {_fmt(claim.score)} ({band}), "
                f"n={claim.n if claim.n is not None else NOT_MEASURED}"
            )
        if claim.sources:
            lines.append(f"  - Cited: {', '.join(_escape(source) for source in claim.sources)}")
        else:
            lines.append("  - Cited: _no evidence linked to this outcome yet_")
    lines.append("")
    return lines


def _render_value(memo: Memo) -> list[str]:
    """*What it is worth* — the recorded estimate, or the one-line reason it is absent."""
    lines = ["## What it is worth", ""]
    if memo.value_estimate is None:
        lines.append(NO_VALUE_NOTE)
        lines.append("")
        return lines
    unit = memo.value_unit or NOT_MEASURED
    size = classify_value(memo)
    detail = (
        f"- `{memo.value_outcome_id}`: {_fmt(memo.value_estimate)} {unit} "
        f"({memo.value_basis}, {size})"
    )
    if memo.value_source:
        detail += f" — source: {_escape(memo.value_source)}"
    if memo.value_n is not None:
        detail += f" — n={memo.value_n}"
    lines.append(detail)
    lines.append("")
    return lines


def render_memo(memo: Memo) -> str:
    """Render the memo as markdown. Deterministic: the same memo yields the same bytes.

    Every section is present only when it has something to say; a missing one is
    replaced by its one-line reason, never placeholder prose and never a zero.
    """
    lines: list[str] = [f"# Decision memo — `{memo.decision_id}`", ""]

    lines.append("## Decision")
    lines.append("")
    if memo.superseded_by:
        lines.append(
            f"_Superseded by `{memo.superseded_by}` on "
            f"{memo.superseded_at or NOT_MEASURED}. The argument below is the record, "
            "not the current choice._"
        )
        lines.append("")
    if memo.chosen:
        for claim in memo.chosen:
            label = f" — {_escape(claim.statement)}" if claim.statement else ""
            lines.append(f"- Chose `{claim.outcome_id}`{label}")
    else:
        lines.append("_No chosen outcome recorded._")
    lines.append(f"- Rationale: {_escape(memo.rationale)}")
    lines.append(
        f"- Decided by {_escape(memo.decided_by)} on {memo.decided_at} ({memo.confidence})"
    )
    lines.append("")

    lines.append("## Why now")
    lines.append("")
    lines.append(_escape(memo.why_now))
    lines.append("")

    lines.extend(_render_claims(memo))

    lines.append("## What we are not doing")
    lines.append("")
    if memo.rejected:
        for rejection in memo.rejected:
            label = f" — {_escape(rejection.statement)}" if rejection.statement else ""
            lines.append(f"- `{rejection.outcome_id}`{label}: {_escape(rejection.reason)}")
    else:
        lines.append("_No rejected options recorded._")
    lines.append("")

    lines.extend(_render_value(memo))

    lines.append("## How we will know")
    lines.append("")
    if memo.criteria:
        lines.extend(f"- {_escape(criterion)}" for criterion in memo.criteria)
    else:
        lines.append(NO_CRITERIA_NOTE)
    if memo.bet is not None:
        lines.append(
            f"- Bet: {_escape(memo.bet.hypothesis)} — target {_fmt(memo.bet.target)} "
            f"by {memo.bet.measure_by}"
        )
    else:
        lines.append(
            "_No bet recorded — no target or measure-by date, so success has no number yet._"
        )
    lines.append("")

    lines.append("## What we do not know")
    lines.append("")
    if memo.holes:
        lines.extend(f"- {_escape(hole)}" for hole in memo.holes)
    else:
        lines.append(NO_HOLES_NOTE)
    lines.append("")

    lines.append("## Sources")
    lines.append("")
    if memo.sources:
        lines.extend(f"- {_escape(source)}" for source in memo.sources)
    else:
        lines.append("_No sources recorded for this decision yet._")
    lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"
