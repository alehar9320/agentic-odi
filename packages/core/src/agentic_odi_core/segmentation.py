"""Derive segment candidates from the scores (D2/ALH-41).

Deterministic grouping over ``(classify_opportunity, importance decile)`` so the
same landscape produces the same candidates on every machine. There is no
clustering dependency and no randomness: a proposal a person cannot reproduce is
a proposal they cannot check.

This module **persists nothing**. A candidate is a proposal; acceptance is
``D2.2``/``ALH-161``. The value here is that the groups announce themselves from
the numbers instead of being invented by a PM (which is how demographics get
into a segmentation).

Two things the readiness gate asked for are pinned in the module docstring
rather than left to a caller:

* **Decile scale.** Importance is already bounded 1–10 (``Outcome.importance``),
  so deciles are computed over that fixed 1–10 range: ``decile = ceil(importance)``
  clamped to 1–10. A score of ``6.4`` lands in decile 7. This is stated, not
  inferred from the fixture, so a boundary is a fact rather than an accident.
* **Dedupe.** ``D2`` names ``similarity.py`` for statement-level dedupe, but that
  helper (``M2-21``/``ALH-85``) is absent. Rather than invent a similarity
  threshold — which would be a fabricated number — this module dedupes on the
  **exact normalised statement** (lowercased, whitespace-collapsed). Two members
  survive only if their statements differ after normalisation. When
  ``similarity.py`` lands the dedupe can tighten without changing the grouping
  contract.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from agentic_odi_core.evaluation import OpportunitySegment, classify_opportunity
from agentic_odi_core.models import Outcome

#: The smallest group worth calling a segment. Below this a "segment" is one
#: person's opinion wearing a label, which is exactly what this feature exists
#: to avoid.
MIN_MEMBERS = 3

#: Importance deciles are taken over this fixed range, not the observed range.
#: Using the observed min/max would move a boundary when one outcome is added,
#: so the same outcome could change decile for no reason of its own.
_IMPORTANCE_MIN = 1.0
_IMPORTANCE_MAX = 10.0


def importance_decile(importance: float | None) -> int | None:
    """Bucket importance into a 1–10 decile over the fixed 1–10 scale.

    ``None`` (unscored) has no decile. A value on a boundary belongs to the
    higher decile, matching how ``classify_opportunity`` treats its own edge.
    """
    if importance is None:
        return None
    clamped = min(max(importance, _IMPORTANCE_MIN), _IMPORTANCE_MAX)
    return int(math.ceil(clamped))


@dataclass(frozen=True)
class SegmentCandidate:
    """A proposed group of outcomes, with the rationale that produced it.

    ``evidence_count`` is the number of member outcomes, **not** a respondent
    count: the landscape records outcomes, not people, and the two must not be
    conflated in a readout. ``fingerprint`` is stable over the membership and the
    grouping key, so a later suggestion can tell "already accepted" from "new"
    without a second table.
    """

    name: str
    members: tuple[str, ...]
    rationale: str
    evidence_count: int
    segment: OpportunitySegment
    decile: int
    fingerprint: str


@dataclass(frozen=True)
class SegmentCandidateSet:
    """Every candidate a landscape yields, plus why there may be none."""

    candidates: tuple[SegmentCandidate, ...] = ()
    reason: str | None = None

    @property
    def has_candidates(self) -> bool:
        return bool(self.candidates)


def _normalise_statement(statement: str) -> str:
    return " ".join(statement.split()).lower()


def _fingerprint(segment: OpportunitySegment, decile: int, members: Sequence[str]) -> str:
    """A stable id over the grouping key and the (already ordered) membership.

    Ids are sorted so a shuffled equivalent input yields the same fingerprint;
    the fingerprint must not depend on the order the caller happened to pass.
    """
    import hashlib

    payload = f"{segment}|{decile}|{'|'.join(sorted(members))}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _decile_label(decile: int) -> str:
    return f"importance decile {decile}"


def _candidate_name(segment: OpportunitySegment, decile: int) -> str:
    """A template name, asserted in tests so nobody believes it was inferred."""
    return f"{segment.capitalize()} outcomes at {_decile_label(decile)}"


def suggest_segment_candidates(outcomes: Iterable[Outcome]) -> SegmentCandidateSet:
    """Group scored outcomes into candidates, deterministically.

    Fewer than :data:`MIN_MEMBERS` scored outcomes yields no candidates and a
    reason saying what is missing — never a candidate made of one datapoint.
    Groups smaller than :data:`MIN_MEMBERS` are dropped (not reported) because
    they are a consequence of the data's shape, not a decision a person must
    make; the caller sees the candidates that clear the bar.
    """
    scored = [outcome for outcome in outcomes if outcome.opportunity_score is not None]
    if len(scored) < MIN_MEMBERS:
        return SegmentCandidateSet(
            reason=(
                f"At least {MIN_MEMBERS} scored outcomes are needed to propose a segment; "
                f"{len(scored)} {'is' if len(scored) == 1 else 'are'} scored."
            )
        )

    # Group by (band, decile) with a stable, content-derived order so a shuffled
    # equivalent input cannot change the output bytes.
    groups: dict[tuple[OpportunitySegment, int], list[Outcome]] = {}
    for outcome in scored:
        band = classify_opportunity(outcome.opportunity_score)
        decile = importance_decile(outcome.importance)
        if decile is None:
            # An opportunity score implies importance, so this is unreachable in
            # practice; skipping rather than guessing keeps it honest if it is.
            continue
        groups.setdefault((band, decile), []).append(outcome)

    candidates: list[SegmentCandidate] = []
    for (band, decile), members in groups.items():
        deduped = _dedupe_by_statement(members)
        if len(deduped) < MIN_MEMBERS:
            continue
        ordered = sorted(deduped, key=lambda o: (o.id,))
        member_ids = tuple(outcome.id for outcome in ordered)
        candidates.append(
            SegmentCandidate(
                name=_candidate_name(band, decile),
                members=member_ids,
                rationale=(
                    f"{len(member_ids)} outcomes are {band} at {_decile_label(decile)} "
                    f"(opportunity > 10 is underserved, = 10 appropriate, < 10 overserved)."
                ),
                evidence_count=len(member_ids),
                segment=band,
                decile=decile,
                fingerprint=_fingerprint(band, decile, member_ids),
            )
        )

    # A stable order across runs: band first (underserved before the rest, since
    # that is the group a strategy starts from), then decile descending.
    band_order = {"underserved": 0, "appropriate": 1, "overserved": 2, "unscored": 3}
    candidates.sort(key=lambda c: (band_order[c.segment], -c.decile, c.name))

    if not candidates:
        return SegmentCandidateSet(
            reason=(
                "No group of at least "
                f"{MIN_MEMBERS} distinct outcomes shares a band and importance decile."
            )
        )
    return SegmentCandidateSet(candidates=tuple(candidates))


def _dedupe_by_statement(members: Sequence[Outcome]) -> list[Outcome]:
    """Drop members whose statement repeats an earlier member's, after normalising.

    Exact-match only, on purpose: ``similarity.py`` is absent and a made-up
    similarity threshold would be a fabricated number. Ties keep the first
    occurrence in id order so the surviving member is deterministic.
    """
    seen: set[str] = set()
    kept: list[Outcome] = []
    for outcome in sorted(members, key=lambda o: o.id):
        key = _normalise_statement(outcome.statement)
        if key in seen:
            continue
        seen.add(key)
        kept.append(outcome)
    return kept
