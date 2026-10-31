"""Stage 6: the innovation strategy the segments imply.

Three paths, and the evidence decides which one is recommended: a differentiated
bet needs an underserved segment on a job that is already served elsewhere, a
disruptive bet needs an overserved segment, and a new-market bet needs outcomes
that map to no job in the store. The rejected paths are recorded with the reason
they were rejected, because a recommendation without its alternatives is a
conclusion.

Nothing here reaches a model or a network: the input is the store's own jobs,
outcomes, and segments.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from agentic_odi_core.evaluation import classify_opportunity
from agentic_odi_core.models import (
    Job,
    Outcome,
    Segment,
    SegmentVerdict,
    Strategy,
    StrategyKind,
)

#: The importance at which a low-cost offer starts looking wrong: the customer
#: rates the outcome highly, so cutting its quality cuts something they want.
_FULL_SERVICE_IMPORTANCE = 8.0


def _scored(outcome: Outcome) -> bool:
    return outcome.importance is not None and outcome.satisfaction is not None


def _underserved_outcomes(outcomes: Sequence[Outcome]) -> list[Outcome]:
    return [
        outcome
        for outcome in outcomes
        if _scored(outcome) and classify_opportunity(outcome.opportunity_score) == "underserved"
    ]


def _served_outcomes(outcomes: Sequence[Outcome]) -> list[Outcome]:
    """Outcomes the market already gets: scored, and nothing above the line."""
    return [
        outcome
        for outcome in outcomes
        if _scored(outcome) and classify_opportunity(outcome.opportunity_score) != "underserved"
    ]


def _statement(outcome: Outcome | None) -> str:
    if outcome is None:
        return "an outcome with no score yet"
    score = "unscored" if outcome.opportunity_score is None else f"{outcome.opportunity_score:g}"
    return f'"{outcome.statement}" ({outcome.id}, score {score})'


@dataclass(frozen=True)
class _Facts:
    """Everything the three builders need, read once from the store."""

    segments: Sequence[Segment]
    jobs: Sequence[Job]
    outcomes: Sequence[Outcome]
    outcomes_by_job: dict[str, list[Outcome]]
    underserved: list[Segment]
    overserved: list[Segment]
    orphans: list[Outcome]

    @classmethod
    def of(
        cls, segments: Sequence[Segment], jobs: Sequence[Job], outcomes: Sequence[Outcome]
    ) -> _Facts:
        known = {job.id for job in jobs}
        return cls(
            segments=segments,
            jobs=jobs,
            outcomes=outcomes,
            outcomes_by_job={job.id: [o for o in outcomes if o.job_id == job.id] for job in jobs},
            underserved=[
                segment
                for segment in segments
                if segment.verdict is SegmentVerdict.UNDERSERVED and segment.outcome_ids
            ],
            overserved=[s for s in segments if s.verdict is SegmentVerdict.OVERSERVED],
            orphans=[outcome for outcome in outcomes if outcome.job_id not in known],
        )

    def gap(self, segment: Segment) -> list[Outcome]:
        owned = self.outcomes_by_job.get(segment.job_id or "", [])
        underserved = _underserved_outcomes(owned)
        return [outcome for outcome in underserved if outcome.id in segment.outcome_ids]


def _differentiated(facts: _Facts) -> tuple[StrategyKind, str, list[str], str | None] | None:
    """The underserved segment whose job is already served elsewhere."""
    for segment in facts.underserved:
        job_outcomes = facts.outcomes_by_job.get(segment.job_id or "", [])
        served = _served_outcomes(job_outcomes)
        if not served:
            continue
        gap = facts.gap(segment) or [
            outcome for outcome in facts.outcomes if outcome.id == segment.outcome_ids[0]
        ]
        target = gap[0] if gap else None
        thesis = (
            f"{segment.people} are underserved on {_statement(target)} while the same job is "
            f"already served on {_statement(served[0])}. Improve the existing product against the "
            "gap instead of building a second one: the job is the same, the unmet need is not."
        )
        bets = [f"Build against {_statement(outcome)} for {segment.people}" for outcome in gap[:3]]
        return StrategyKind.DIFFERENTIATED, thesis, bets, segment.id
    return None


def _disruptive(facts: _Facts) -> tuple[StrategyKind, str, list[str], str | None] | None:
    """An overserved segment: they have the outcome and are not asking for more."""
    if not facts.overserved:
        return None
    segment = facts.overserved[0]
    owned = [outcome for outcome in facts.outcomes if outcome.id in segment.outcome_ids]
    top = owned[0] if owned else None
    heavy = [
        outcome for outcome in owned if (outcome.importance or 0.0) >= _FULL_SERVICE_IMPORTANCE
    ]
    if heavy:
        caveat = (
            f"{len(heavy)} of these outcomes is rated at or above "
            f"{_FULL_SERVICE_IMPORTANCE:g} importance, which weakens the case: this reads as a "
            "full-service purchase, and a cheaper offer would take something they rely on."
        )
    else:
        caveat = (
            "Nothing here is a full-service purchase, so a simpler offer does not have to "
            "promise less of what they already rely on."
        )
    thesis = (
        f"{segment.people} already get {_statement(top)} and are not asking for more. The way to "
        f"win this segment is a lower-cost, simpler offer that does the same job with fewer "
        f"moving parts. {caveat}"
    )
    bets = [
        f"Price a stripped-down version that still delivers {_statement(outcome)}"
        for outcome in owned[:3]
    ]
    return StrategyKind.DISRUPTIVE, thesis, bets, segment.id


def _new_market(facts: _Facts) -> tuple[StrategyKind, str, list[str], str | None] | None:
    """Outcomes that map to no job in the store: a job nobody serves today."""
    if not facts.orphans:
        return None
    named = ", ".join(_statement(outcome) for outcome in facts.orphans[:3])
    thesis = (
        f"{len(facts.orphans)} outcome(s) map to no job in the store: {named}. That is a job "
        "nobody is being served on today, so the bet is a new market rather than a better "
        "version of an existing product."
    )
    bets = [
        f"Define the job behind {_statement(outcome)} before scoring anything against it"
        for outcome in facts.orphans[:3]
    ]
    return StrategyKind.NEW_MARKET, thesis, bets, None


BuildPath = Callable[[_Facts], tuple[StrategyKind, str, list[str], str | None] | None]

_BUILDERS: tuple[BuildPath, ...] = (
    _differentiated,
    _disruptive,
    _new_market,
)


def _rejected_reason(kind: StrategyKind, facts: _Facts) -> str:
    if kind is StrategyKind.DIFFERENTIATED:
        if not facts.underserved:
            return (
                "no segment is underserved, so there is nothing for an existing product to "
                "improve against"
            )
        if not any(
            _served_outcomes(facts.outcomes_by_job.get(segment.job_id or "", []))
            for segment in facts.underserved
        ):
            return (
                "the underserved segments sit on jobs with no served outcomes, so there is no "
                "existing product to differentiate from"
            )
        return "another path has stronger evidence right now"
    if kind is StrategyKind.DISRUPTIVE:
        if not facts.overserved:
            return (
                f"none of the {len(facts.segments)} segment(s) is overserved, so a low-cost offer "
                "has nobody to win"
            )
        return "an underserved segment is the better place to spend"
    if facts.orphans:
        return "the job those outcomes describe is already in the store, so the market is not new"
    return (
        "every outcome maps to a job already in the store, so there is no job that is entirely "
        "unaddressed"
    )


def _strategy_id(kind: StrategyKind, segment_id: str | None) -> str:
    """Stable id for the bet on this path, so re-proposing updates rather than piles up."""
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f"strategy|{kind.value}|{segment_id or ''}"))


def propose_strategy(
    segments: Sequence[Segment],
    jobs: Sequence[Job],
    outcomes: Sequence[Outcome],
) -> Strategy | None:
    """Return the one strategy the evidence supports, or ``None``.

    ``None`` is the honest answer when no path has evidence behind it: with no
    segments and no orphaned outcomes there is nothing to recommend, and
    inventing a bet is the fabrication this stage exists to avoid. Exactly one
    kind is recommended, and ``rejected`` carries the other two with reasons.
    """
    facts = _Facts.of(segments, jobs, outcomes)
    for build in _BUILDERS:
        chosen = build(facts)
        if chosen is None:
            continue
        kind, thesis, bets, segment_id = chosen
        return Strategy(
            id=_strategy_id(kind, segment_id),
            kind=kind,
            segment_id=segment_id,
            thesis=thesis,
            bets=bets,
            rejected=[
                {"kind": other.value, "why": _rejected_reason(other, facts)}
                for other in StrategyKind
                if other is not kind
            ],
        )
    return None


__all__ = ["propose_strategy"]
