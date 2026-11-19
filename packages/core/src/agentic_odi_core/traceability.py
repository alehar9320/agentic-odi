"""Traceability: what an outcome advances, and what the vision dropped.

An outcome is only worth funding if it advances something the strategy names.
This module answers the three failures a strategy review cares about, and
nothing else:

* **orphans** — outcomes that carry no link at all, so they advance nothing.
* **unfunded** — objectives (a V2MOM method or measure) that no outcome
  advances.
* **drift** — links whose objective text is no longer in the vision: the
  objective was reworded or removed, so the link points at something the vision
  dropped.

The report is read-only. It never repairs a link, never invents an objective,
and never counts an unlinked outcome as drift. When there is no vision to check
against it says so, rather than returning three empty sections that read as a
clean bill of health.

Matching is exact: a link is compared by its frozen content key, and the key is
re-derived only from the text stored at link time, never from a current rule.
Nothing here is fuzzy or similarity-based, because a report that guesses which
objective an outcome meant is worse than one that reports drift and lets a
person relink.
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field

from agentic_odi_core.models import V2MOM, Outcome

#: ``(V2MOM attribute, canonical field name)`` for the lists an outcome may
#: advance. The vision is a statement, values are principles, and obstacles are
#: risks, so none of them is a target.
OBJECTIVE_FIELDS: tuple[tuple[str, str], ...] = (("methods", "method"), ("measures", "measure"))

#: The number of hex characters in a content key. Twelve hex is 48 bits: a
#: birthday collision needs roughly 16 million distinct objectives, far beyond
#: a strategy document.
KEY_LENGTH = 12


def normalize_objective(text: str) -> str:
    """Canonical form for matching a link to an objective.

    NFC, whitespace collapsed, casefolded, trailing punctuation stripped. This
    is frozen: the report must never re-derive an existing key under new rules,
    or a normalization change would silently drift every link at once.
    """
    normalized = unicodedata.normalize("NFC", text)
    normalized = " ".join(normalized.split())
    return normalized.casefold().rstrip(".,;:!?—- ")


def objective_key(field_name: str, text: str) -> str:
    """The frozen content key for an objective: sha256 over field and text.

    ``field_name`` is the canonical ``method``/``measure``, not the V2MOM list
    attribute, so the same text in two lists never shares a key.
    """
    payload = f"{field_name}\x1f{normalize_objective(text)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:KEY_LENGTH]


@dataclass(frozen=True)
class Objective:
    """One entry in the vision that outcomes can advance."""

    field: str
    text: str

    @property
    def key(self) -> str:
        return objective_key(self.field, self.text)

    def as_dict(self) -> dict[str, str]:
        return {"field": self.field, "key": self.key, "text": self.text}


@dataclass(frozen=True)
class TraceLink:
    """One outcome's claim that it advances an objective.

    ``text`` is the objective text recorded at link time, so a reworded
    objective leaves this text behind as the drift evidence.
    """

    outcome_id: str
    field: str
    text: str

    @property
    def key(self) -> str:
        return objective_key(self.field, self.text)


@dataclass
class TraceabilityReport:
    """The three failures, each naming the ids behind it.

    ``objectives_defined`` is False when the vision carries no methods or
    measures at all. That is a distinct state from "everything is fine": an
    empty vision is not a clean report, and ``message`` says so.
    """

    objectives_defined: bool = False
    message: str | None = None
    orphans: list[str] = field(default_factory=list)
    unfunded: list[dict[str, str]] = field(default_factory=list)
    drift: list[dict[str, str]] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "orphans": len(self.orphans),
            "unfunded": len(self.unfunded),
            "drift": len(self.drift),
        }

    def as_dict(self) -> dict[str, object]:
        return {
            "objectives_defined": self.objectives_defined,
            "message": self.message,
            "orphans": list(self.orphans),
            "unfunded": [dict(item) for item in self.unfunded],
            "drift": [dict(item) for item in self.drift],
            "counts": self.counts,
        }

    def summary(self) -> str:
        """One line a person can read, or the honest "nothing to check" line."""
        if self.message is not None:
            return self.message
        if not (self.orphans or self.unfunded or self.drift):
            return "Every outcome advances an objective, and every objective is funded."
        return (
            f"{len(self.unfunded)} objective(s) have no outcome behind them; "
            f"{len(self.orphans)} outcome(s) advance nothing; "
            f"{len(self.drift)} link(s) point at something the vision dropped."
        )


def objectives_from_v2mom(v2mom: V2MOM | None) -> list[Objective]:
    """Every method and measure in the vision, in the order they are stored."""
    if v2mom is None:
        return []
    objectives: list[Objective] = []
    for attribute, field_name in OBJECTIVE_FIELDS:
        for text in getattr(v2mom, attribute):
            stripped = text.strip()
            if stripped:
                objectives.append(Objective(field=field_name, text=stripped))
    return objectives


def links_from_outcomes(outcomes: Sequence[Outcome]) -> list[TraceLink]:
    """Every recorded link, read from the outcomes that carry it."""
    return [
        TraceLink(outcome_id=outcome.id, field=alignment.field, text=alignment.text)
        for outcome in outcomes
        for alignment in outcome.trace
    ]


def compute_traceability_report(
    v2mom: V2MOM | None,
    outcomes: Sequence[Outcome],
    links: Sequence[TraceLink] | None = None,
) -> TraceabilityReport:
    """Compute orphans, unfunded objectives, and drift.

    An outcome with no link is an orphan; an objective no link resolves to is
    unfunded; a link whose text is not in the current vision has drifted.
    Unlinked outcomes are never drift. ``links`` defaults to the links carried
    by ``outcomes``; it is accepted explicitly so the pure computation can be
    exercised against a hand-built fixture.
    """
    objectives = objectives_from_v2mom(v2mom)
    if not objectives:
        return TraceabilityReport(
            objectives_defined=False,
            message=(
                "No objectives defined: add a method or a measure to the vision "
                "before a traceability report can say anything."
            ),
        )

    resolved_links = links_from_outcomes(outcomes) if links is None else links
    current_keys = {objective.key for objective in objectives}

    linked_outcome_ids = {link.outcome_id for link in resolved_links}
    orphans = [outcome.id for outcome in outcomes if outcome.id not in linked_outcome_ids]

    drift: list[dict[str, str]] = []
    seen_drift: set[tuple[str, str, str]] = set()
    for link in resolved_links:
        if link.key in current_keys:
            continue
        signature = (link.outcome_id, link.field, link.key)
        if signature in seen_drift:
            continue
        seen_drift.add(signature)
        drift.append(
            {
                "outcome_id": link.outcome_id,
                "field": link.field,
                "key": link.key,
                "text": link.text,
            }
        )

    funded_keys = {link.key for link in resolved_links if link.key in current_keys}
    unfunded = [objective.as_dict() for objective in objectives if objective.key not in funded_keys]

    return TraceabilityReport(
        objectives_defined=True,
        message=None,
        orphans=orphans,
        unfunded=unfunded,
        drift=drift,
    )


__all__ = [
    "KEY_LENGTH",
    "OBJECTIVE_FIELDS",
    "Objective",
    "TraceLink",
    "TraceabilityReport",
    "compute_traceability_report",
    "links_from_outcomes",
    "normalize_objective",
    "objective_key",
    "objectives_from_v2mom",
]
