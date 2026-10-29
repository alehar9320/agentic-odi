"""The trust seams the later Pillar-2 increments fill in.

B1 and B6 are implemented: every score carries its sample and method, and every
accepted score change is written to an append-only history. The remaining
increments — reproducible bands (B3), honest ranking (B4) and read-side history
with signed deltas (B6.1) — each depend on a decision that is still open, so
they are *interfaces* here rather than invented defaults.

Every function in this module is a seam: it names the contract the increment
must satisfy and refuses to answer until that contract is approved. The
repository's guardrails forbid turning an unknown into a fact, so a caller that
reaches a seam before its gate clears gets an explicit refusal naming the
blocking decision — never a fabricated band, confidence class or direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agentic_odi_core.errors import OdiError
from agentic_odi_core.models import Outcome, ScoreSnapshot

#: The open decisions from the Pillar-2 spec, named so a refusal can cite one.
BootstrapConvention = "bootstrap convention (B3)"
ConfidenceTable = "confidence table (B4.1)"
DeltaSemantics = "delta semantics (B6.1)"

DeltaDirection = Literal["up", "down", "flat"]


class TrustContractPendingError(OdiError):
    """A later-increment contract is not approved yet.

    Raised instead of returning a fabricated value. ``capability`` is the seam
    that was reached and ``decision`` is the open decision blocking it, so the
    message says exactly what must be approved before the call can succeed.
    """

    def __init__(self, capability: str, decision: str) -> None:
        self.capability = capability
        self.decision = decision
        super().__init__(f"{capability} is not available until the {decision} decision is approved")


@dataclass(frozen=True)
class OpportunityInterval:
    """A band around an opportunity score, not a point.

    Interface only: the percentile-bootstrap convention is the B3 gate, so no
    code constructs one yet. The shape is fixed so consumers (ranking, the
    landscape, the explain surface) can be written against it.
    """

    outcome_id: str
    low: float
    high: float
    confidence_level: float
    n: int


@dataclass(frozen=True)
class OutcomeDelta:
    """The signed change between two accepted score states.

    Interface only: baseline selection, missing-dimension behaviour and the
    definition of ``direction`` are the B6.1 gate.
    """

    outcome_id: str
    importance: float | None
    satisfaction: float | None
    opportunity: float | None
    direction: DeltaDirection


def opportunity_interval(outcome: Outcome) -> OpportunityInterval:
    """The percentile-bootstrap band for an outcome's score (B3).

    Gated on the bootstrap-convention decision: confidence level, percentile
    extraction/interpolation, singleton/empty handling and runtime
    reproducibility must be approved first, so this refuses rather than pick a
    convention the issue has not accepted.
    """
    raise TrustContractPendingError("opportunity_interval", BootstrapConvention)


def classify_confidence(outcome: Outcome) -> Literal["measured", "thin", "none"]:
    """Classify how much evidence stands behind a score (B4.1).

    Gated on the confidence-table decision: unknown/unequal counts, estimates
    and one-response surveys must be mapped to a class by an approved table, so
    this refuses rather than guess which bucket an unknown falls into.
    """
    raise TrustContractPendingError("classify_confidence", ConfidenceTable)


def outcome_delta(snapshots: list[ScoreSnapshot], since: str | None = None) -> OutcomeDelta:
    """The signed change from a baseline snapshot to the latest (B6.1).

    Gated on the delta-semantics decision: which snapshot is the baseline, how a
    missing dimension is treated and what ``direction`` means must be approved
    first. The persisted input already exists — this reads it, and refuses until
    the sign policy is fixed.
    """
    raise TrustContractPendingError("outcome_delta", DeltaSemantics)
