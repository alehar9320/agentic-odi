"""Stage 5: outcome-based market segmentation.

A segment is a group of people plus a functional job, and the outcomes are the
evidence for it — so the grouping is done on the job map, never on who the
customer is. Nothing in this module reads a demographic, firmographic, or
industry attribute, and there is a test that pins that: the output is identical
when such a field is added to the inputs.

The default strategy is deliberately dumb and deterministic: group a job's
outcomes by the step they attach to, keep the groups with enough evidence to be
called a segment, and report the rest as unclustered rather than inflating a
single outcome into a market.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from agentic_odi_core.evaluation import UNDERSERVED_SCORE, classify_opportunity
from agentic_odi_core.models import Job, Outcome, Segment, SegmentVerdict, Step

#: A group of one is a hypothesis, not a segment.
MIN_OUTCOMES_PER_SEGMENT = 2

#: The outcome count at which a cluster is treated as fully evidenced.
_FULL_EVIDENCE_COUNT = 4

_OBJECT_OF_CONTROL = re.compile(
    r"\bthe\s+(?P<phrase>.+?)(?:\s+(?:when|while|before|after|during|if|as)\b|$)",
    re.IGNORECASE,
)


def _scored(outcome: Outcome) -> bool:
    return outcome.importance is not None and outcome.satisfaction is not None


def segment_verdict(outcomes: Sequence[Outcome]) -> SegmentVerdict | None:
    """Classify a segment by the opportunity scores of its outcomes.

    Underserved          — at least one outcome above the ``> 10`` threshold.
    Overserved           — every outcome has satisfaction at or above importance.
    Appropriately served — every outcome is scored, and none is above 10.
    ``None``             — any outcome is unscored, or there are none at all.
    A group that cannot be classified is reported as such; it is never guessed.
    """
    if not outcomes or not all(_scored(outcome) for outcome in outcomes):
        return None
    if any(
        classify_opportunity(outcome.opportunity_score) == "underserved" for outcome in outcomes
    ):
        return SegmentVerdict.UNDERSERVED
    if all(
        outcome.satisfaction is not None
        and outcome.importance is not None
        and outcome.satisfaction >= outcome.importance
        for outcome in outcomes
    ):
        return SegmentVerdict.OVERSERVED
    return SegmentVerdict.APPROPRIATELY_SERVED


class SegmentationStrategy(Protocol):
    """How outcomes become segments. Swappable, so a smarter clusterer can
    replace the default without touching the service, the store, or the tools."""

    def segment(self, jobs: Sequence[Job], outcomes: Sequence[Outcome]) -> list[Segment]: ...


@dataclass(frozen=True)
class OutcomeClusterStrategy:
    """Group a job's outcomes by the step they attach to.

    ``steps`` names the clusters; the protocol signature stays two arguments.
    ``people`` is the group described in the person's own words when the caller
    has them — anything derived here is labelled as inferred.
    """

    steps: Sequence[Step] = field(default_factory=tuple)
    people: str | None = None

    def segment(self, jobs: Sequence[Job], outcomes: Sequence[Outcome]) -> list[Segment]:
        segments: list[Segment] = []
        for job in jobs:
            job_outcomes = [outcome for outcome in outcomes if outcome.job_id == job.id]
            for step_id, group in _by_step(job_outcomes):
                if len(group) < MIN_OUTCOMES_PER_SEGMENT:
                    continue
                segments.append(self._build(job, step_id, group, job_outcomes))
        return segments

    # -- one segment per cluster -------------------------------------------

    def _build(
        self,
        job: Job,
        step_id: str | None,
        group: list[Outcome],
        job_outcomes: list[Outcome],
    ) -> Segment:
        step = next(
            (item for item in self.steps if item.id == step_id and item.job_id == job.id),
            None,
        )
        step_label = step.name if step is not None else "the job as a whole"
        verdict = segment_verdict(group)
        people, inferred = self._people(group)
        label = step_label if step is not None else job.name
        share = len(group) / len(job_outcomes) if job_outcomes else 1.0
        size = min(len(group) / _FULL_EVIDENCE_COUNT, 1.0)
        return Segment(
            id=_cluster_id(job.id, step_id),
            job_id=job.id,
            name=f"{people}, {label}",
            people=people,
            people_inferred=inferred,
            job_statement=job.description or job.name,
            outcome_ids=[outcome.id for outcome in group],
            verdict=verdict,
            rationale=self._rationale(verdict, group, step_label, inferred, share),
            confidence=round(0.5 * share + 0.5 * size, 2),
        )

    def _people(self, group: Sequence[Outcome]) -> tuple[str, bool]:
        supplied = (self.people or "").strip()
        if supplied:
            return supplied, False
        shared = _shared_object(group)
        if shared is None:
            return "the people this job describes", True
        return f"the people working on the {shared}", True

    def _rationale(
        self,
        verdict: SegmentVerdict | None,
        group: Sequence[Outcome],
        step_label: str,
        inferred: bool,
        share: float,
    ) -> str:
        scores = ", ".join(
            f"{outcome.id}={_format(outcome.opportunity_score)}"
            for outcome in group
            if outcome.opportunity_score is not None
        )
        parts = [
            f"{len(group)} outcomes on {step_label} ({share:.0%} of the job's outcomes)",
            _VERDICT_EXPLANATION[verdict] if verdict in _VERDICT_EXPLANATION else "no verdict",
        ]
        if scores:
            parts.append(f"scores: {scores}")
        else:
            parts.append("no outcome in this group is scored")
        if inferred:
            parts.append("the group was inferred from the outcomes, not named by the user")
        return "; ".join(parts) + "."


_VERDICT_EXPLANATION: dict[SegmentVerdict, str] = {
    SegmentVerdict.UNDERSERVED: (
        f"underserved: at least one outcome scores above {UNDERSERVED_SCORE:g}"
    ),
    SegmentVerdict.OVERSERVED: "overserved: satisfaction is at or above importance everywhere",
    SegmentVerdict.APPROPRIATELY_SERVED: "appropriately served: scored, and nothing above the line",
}


def _cluster_id(job_id: str, step_id: str | None) -> str:
    """Stable id for a (job, step) cluster, so re-segmenting updates one record.

    Keyed on the cluster's identity rather than its members: new evidence
    strengthens the same segment instead of creating a second one beside it.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_OID, f"segment|{job_id}|{step_id or ''}"))


def _by_step(outcomes: Sequence[Outcome]) -> list[tuple[str | None, list[Outcome]]]:
    """Outcomes grouped by step, in first-seen order, so the run is stable."""
    groups: dict[str | None, list[Outcome]] = {}
    for outcome in outcomes:
        groups.setdefault(outcome.step_id, []).append(outcome)
    return list(groups.items())


def _shared_object(group: Sequence[Outcome]) -> str | None:
    """The object of control most of the statements share, if any does."""
    phrases: list[str] = []
    for outcome in group:
        match = _OBJECT_OF_CONTROL.search(outcome.statement)
        if match is not None:
            phrase = match.group("phrase").strip(" .,;:")
            if phrase:
                phrases.append(phrase.lower())
    if not phrases:
        return None
    counts = Counter(phrases)
    top = counts.most_common()
    best = top[0][1]
    winners = sorted(phrase for phrase, count in top if count == best)
    return winners[0] if len(winners) == 1 else None


def _format(value: float | None) -> str:
    return "—" if value is None else f"{value:g}"


def unclustered_outcomes(
    segments: Sequence[Segment],
    outcomes: Sequence[Outcome],
) -> list[Outcome]:
    """Outcomes that joined no segment: a cluster of one, or a job nobody maps.

    These are reported, never dropped — a single outcome is evidence for a
    hypothesis, and an outcome whose job is not in the store is the raw material
    for a new-market bet, not a segment.
    """
    clustered = {outcome_id for segment in segments for outcome_id in segment.outcome_ids}
    return [outcome for outcome in outcomes if outcome.id not in clustered]
