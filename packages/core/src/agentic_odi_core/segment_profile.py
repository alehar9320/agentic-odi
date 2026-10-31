"""Underserved vs overserved, per segment (D3/ALH-42).

A read-only projection: it writes nothing, and it defines no threshold of its
own. Servability is ``evaluation.classify_opportunity``'s existing boundary
(> 10 underserved, = 10 appropriate, < 10 overserved), so a profile cannot
disagree with the rest of the product about what "underserved" means.

The two halves of an ODI strategy are returned **separately**
(``top_underserved`` and ``top_overserved``): merging them into one ranked list
would destroy exactly the distinction a strategy choice rests on.

Honest empties, pinned here so no caller has to decide them again:

* An empty segment reports **zeroed keys**, not omitted ones.
* ``measured_ratio`` is ``measured / total`` where ``total`` is the segment's
  stored membership. With zero measured outcomes the ratio is ``None`` — a ratio
  of nothing is not zero — and the reason is stated in ``gaps``.
* ``total`` is a count of *outcomes*, never a respondent sample. The profile says
  so rather than letting a reader assume the members are people.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from agentic_odi_core.evaluation import OpportunitySegment, classify_opportunity
from agentic_odi_core.models import Outcome, Segment

#: How many of each half the profile shows. A top-three is a reading aid, not a
#: cut: the counts above it carry the full picture.
TOP_LIMIT = 3


@dataclass(frozen=True)
class ProfileEntry:
    """One member outcome as the profile shows it."""

    outcome_id: str
    statement: str
    score: float
    band: OpportunitySegment


@dataclass(frozen=True)
class SegmentProfile:
    """A segment's servability, split into the two halves a strategy needs."""

    segment_id: str
    segment_name: str
    total_members: int = 0
    measured_count: int = 0
    unscored_count: int = 0
    missing_count: int = 0
    underserved_count: int = 0
    appropriate_count: int = 0
    overserved_count: int = 0
    top_underserved: tuple[ProfileEntry, ...] = ()
    top_overserved: tuple[ProfileEntry, ...] = ()
    #: ``measured / total``; ``None`` when nothing is measured, never ``0.0``.
    measured_ratio: float | None = None
    #: Plain-language notes: what is missing and why a list may be empty.
    gaps: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ratio_denominator(self) -> str:
        """What ``measured_ratio`` divides by, stated so nobody assumes people."""
        return "member outcomes"


def build_segment_profile(
    segment: Segment,
    members: Sequence[Outcome],
    missing_ids: Sequence[str] = (),
) -> SegmentProfile:
    """Build a segment's profile from its resolved members.

    ``members`` are the stored member outcomes that still resolve; ``missing_ids``
    are stored members that no longer exist. A missing member is reported, not
    silently dropped: an unresolvable id is a gap in the record, and pretending
    the segment shrank would hide it.
    """
    scored = [outcome for outcome in members if outcome.opportunity_score is not None]
    unscored = [outcome for outcome in members if outcome.opportunity_score is None]

    measured: list[ProfileEntry] = [
        ProfileEntry(
            outcome_id=outcome.id,
            statement=outcome.statement,
            score=outcome.opportunity_score,  # type: ignore[arg-type]
            band=classify_opportunity(outcome.opportunity_score),
        )
        for outcome in scored
    ]

    underserved = [entry for entry in measured if entry.band == "underserved"]
    appropriate = [entry for entry in measured if entry.band == "appropriate"]
    overserved = [entry for entry in measured if entry.band == "overserved"]

    total = len(members) + len(missing_ids)
    # A ratio of nothing is not zero: with no measured outcome the ratio is
    # ``None`` and the reason is stated in ``gaps``. ``total`` is the segment's
    # stored membership, never a respondent sample.
    measured_ratio: float | None = None if not measured else len(measured) / total

    gaps: list[str] = []
    if total == 0:
        gaps.append("This segment has no members.")
    if measured == [] and total > 0:
        gaps.append("No member outcome is scored, so no servability can be read.")
    if unscored:
        gaps.append(f"{len(unscored)} member outcome(s) are unscored and are excluded above.")
    if missing_ids:
        gaps.append(
            f"{len(missing_ids)} stored member(s) no longer resolve: "
            f"{', '.join(sorted(missing_ids))}."
        )

    return SegmentProfile(
        segment_id=segment.id,
        segment_name=segment.name,
        total_members=total,
        measured_count=len(measured),
        unscored_count=len(unscored),
        missing_count=len(missing_ids),
        underserved_count=len(underserved),
        appropriate_count=len(appropriate),
        overserved_count=len(overserved),
        top_underserved=tuple(_top(underserved)),
        top_overserved=tuple(_top(overserved)),
        measured_ratio=measured_ratio,
        gaps=tuple(gaps),
    )


def _top(entries: list[ProfileEntry]) -> list[ProfileEntry]:
    """The top :data:`TOP_LIMIT` entries, highest score first, id as the tie-break.

    The tie-break is the id, so two outcomes with the same score order the same
    way on every machine.
    """
    return sorted(entries, key=lambda entry: (-entry.score, entry.outcome_id))[:TOP_LIMIT]
