"""The trust seams the later Pillar-2 increments fill in.

B1 and B6 are implemented: every score carries its sample and method, and every
accepted score change is written to an append-only history. The remaining
increments — survey import (B2), reproducible bands (B3/B3.1/B3.2), honest
ranking (B4/B4.1) and read-side history with signed deltas (B6.1) — each depend
on a decision that is still open, so they are *interfaces* here rather than
invented defaults.

Every function in this module is a seam: it names the contract the increment
must satisfy and refuses to answer until that contract is approved. The
repository's guardrails forbid turning an unknown into a fact, so a caller that
reaches a seam before its gate clears gets an explicit refusal naming the
blocking decision — never a fabricated band, confidence class, aggregate or
direction.

The shapes (the dataclasses) are fixed here so consumers — ranking, the
landscape, the explain surface, the CLI — can be written against them before
the gate clears; only the *answers* wait on the decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agentic_odi_core.errors import OdiError
from agentic_odi_core.models import Outcome, ScoreSnapshot

#: The open decisions from the Pillar-2 spec, named so a refusal can cite one.
ImportPolicy = "import policy (B2)"
RetentionPolicy = "retention policy (B3.1)"
IntervalProvenancePolicy = "interval-provenance decision (B3.2)"
BootstrapConvention = "bootstrap convention (B3)"
ConfidenceTable = "confidence table (B4.1)"
DeltaSemantics = "delta semantics (B6.1)"

DeltaDirection = Literal["up", "down", "flat"]
ConfidenceClass = Literal["measured", "thin", "none"]


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


def classify_confidence(outcome: Outcome) -> ConfidenceClass:
    """Classify how much evidence stands behind a score (B4.1).

    Gated on the confidence-table decision: unknown/unequal counts, estimates
    and one-response surveys must be mapped to a class by an approved table, so
    this refuses rather than guess which bucket an unknown falls into.
    """
    raise TrustContractPendingError("classify_confidence", ConfidenceTable)


@dataclass(frozen=True)
class SurveyAggregate:
    """One outcome's sample mean, pulled from imported survey responses (B2).

    Interface only: the p10/p90 quantile convention, duplicate/missing-row
    handling and repeated-import policy are the B2 gate, so no code builds one
    yet. The shape lets the importer, the CLI report and the persistence layer
    be written against a single contract.
    """

    outcome_id: str
    importance: float
    satisfaction: float
    importance_n: int
    satisfaction_n: int


@dataclass(frozen=True)
class RetainedSurveyInput:
    """The paired per-respondent inputs an interval is reproduced from (B3.1).

    Interface only: what is retained, for how long, and how a re-import relates
    to the previous one is the B3.1 gate. Without retained pairs a band cannot
    be recomputed, only remembered, so this shape is fixed before the store.
    """

    outcome_id: str
    respondent_id: str
    importance: float
    satisfaction: float


@dataclass(frozen=True)
class IntervalProvenance:
    """Where a persisted band came from, and whether it is still valid (B3.2).

    Interface only: the provenance fields, the staleness rule (which score edit
    invalidates a band) and how invalidation is recorded are the B3.2 gate. A
    band with no provenance cannot be trusted after an edit, so this shape names
    the fields a consumer may rely on.
    """

    outcome_id: str
    low: float
    high: float
    confidence_level: float
    n: int
    seed: int | None
    method: str
    computed_at: str
    stale: bool


def parse_survey(rows: list[dict[str, object]]) -> list[RetainedSurveyInput]:
    """Parse raw survey rows into retained paired inputs (B2).

    Gated on the import-policy decision: duplicate respondents, missing
    dimensions, unmatched outcome statements and repeated imports must be
    resolved by an approved policy first, so this refuses rather than silently
    drop or double-count a row.
    """
    raise TrustContractPendingError("parse_survey", ImportPolicy)


def aggregate_survey(inputs: list[RetainedSurveyInput]) -> list[SurveyAggregate]:
    """Aggregate retained inputs into one mean per outcome (B2).

    Gated on the same import-policy decision as :func:`parse_survey`: without it
    a mean could be taken over an unapproved set of rows, which is exactly the
    fabricated fact the pillar forbids.
    """
    raise TrustContractPendingError("aggregate_survey", ImportPolicy)


def retain_survey_inputs(inputs: list[RetainedSurveyInput]) -> list[RetainedSurveyInput]:
    """Persist the paired inputs a band will later be recomputed from (B3.1).

    Gated on the retention-policy decision: response retention/deletion and
    study/wave lineage must be approved before raw respondent rows are stored.
    """
    raise TrustContractPendingError("retain_survey_inputs", RetentionPolicy)


def persisted_interval(outcome: Outcome, snapshots: list[ScoreSnapshot]) -> IntervalProvenance:
    """Read a persisted band and its provenance, or refuse (B3.2).

    Gated on the interval-provenance decision and the bootstrap convention it
    inherits: which fields are persisted and what makes a band stale are not yet
    approved, so this refuses rather than return a band with no lineage.
    """
    raise TrustContractPendingError("persisted_interval", IntervalProvenancePolicy)


def rank_outcomes_honestly(outcomes: list[Outcome]) -> list[Outcome]:
    """Rank outcomes without mixing unknown scores into zeroes (B4).

    Gated on the confidence-table decision: an outcome with no evidence must be
    classified (B4.1) before it can be placed, so this refuses rather than sort
    an unknown as if it were measured. The existing :func:`rank_outcomes` keeps
    its behaviour; this names the honest ranking the increment must add.
    """
    raise TrustContractPendingError("rank_outcomes_honestly", ConfidenceTable)


def outcome_delta(snapshots: list[ScoreSnapshot], since: str | None = None) -> OutcomeDelta:
    """The signed change from a baseline snapshot to the latest (B6.1).

    Gated on the delta-semantics decision: which snapshot is the baseline, how a
    missing dimension is treated and what ``direction`` means must be approved
    first. The persisted input already exists — this reads it, and refuses until
    the sign policy is fixed.
    """
    raise TrustContractPendingError("outcome_delta", DeltaSemantics)
