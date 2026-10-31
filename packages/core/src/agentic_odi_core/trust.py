"""The trust surfaces of Pillar 2, with their provisional conventions.

B1 and B6 are implemented: every score carries its sample and method, and every
accepted score change is written to an append-only history.

The later increments were originally *seams* that refused until a decision was
approved. They are now implemented against a **named provisional convention** so
the product works end to end, while the convention itself stays visible and
swappable in one place. The distinction matters: an unknown must never be turned
into a fact silently, so each convention is documented, cited in a refusal when
its inputs are missing, and pinned by tests.

Provisional conventions (each names the decision it stands in for):

* B2 survey import -- the import policy lives in :mod:`agentic_odi_core.survey`.
* B3 interval -- the percentile-bootstrap convention lives in
  :mod:`agentic_odi_core.stats`; :func:`opportunity_interval` adapts an outcome
  to it and returns a *no-band* placeholder for an estimate.
* B3.1 retention -- :func:`retain_survey_inputs` is an in-memory stub: it keeps
  the paired inputs for the process lifetime and performs no deletion, because
  the retention/deletion and study-lineage policy is not yet approved. Its read
  side, :func:`retained_survey_inputs`, refuses when nothing was retained for an
  outcome rather than returning an empty list that would read as "zero
  responses".
* B3.2 provenance -- :func:`persisted_interval` reads the stored band and its
  provenance off the outcome, and reports a band stale when the score it was
  computed from has since moved.
* B4.1 confidence -- :func:`classify_confidence` maps evidence to
  measured/thin/none through :data:`MEASURED_SAMPLE_THRESHOLD`.
* B6.1 delta -- :func:`outcome_delta` reads two snapshots and signs the change
  through :data:`DELTA_TOLERANCE`.

A convention is not a measurement: :class:`TrustContractPendingError` still
exists and is raised when the inputs a convention needs are *absent* (no sample,
no baseline), so a caller is told what is missing instead of being handed a
fabricated band, class or direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agentic_odi_core.errors import OdiError, ValidationError
from agentic_odi_core.models import Outcome, ScoreSnapshot
from agentic_odi_core.stats import (
    DEFAULT_CONFIDENCE_LEVEL,
    DEFAULT_SAMPLES,
    DEFAULT_SEED,
    Interval,
)
from agentic_odi_core.stats import (
    opportunity_interval as _bootstrap_interval,
)
from agentic_odi_core.survey import (
    SurveyAggregate,
    SurveyImportResult,
    SurveyResponse,
)
from agentic_odi_core.survey import (
    aggregate_survey as _aggregate_survey,
)
from agentic_odi_core.survey import (
    parse_survey as _parse_survey,
)

#: The open decisions, named so a refusal can cite one.
ImportPolicy = "import policy (B2)"
RetentionPolicy = "retention policy (B3.1)"
IntervalProvenancePolicy = "interval-provenance decision (B3.2)"
BootstrapConvention = "bootstrap convention (B3)"
ConfidenceTable = "confidence table (B4.1)"
DeltaSemantics = "delta semantics (B6.1)"

DeltaDirection = Literal["up", "down", "flat"]
ConfidenceClass = Literal["measured", "thin", "none"]

#: B4.1 provisional table. A survey or import with a sample at or above the
#: measured threshold is "measured"; a smaller sample is "thin"; an estimate, an
#: unknown count or no score at all is "none". The threshold and the exact
#: bucketing are the B4.1 gate, so they are named here, not inlined at call sites.
MEASURED_SAMPLE_THRESHOLD = 30

#: B6.1 provisional semantics. ``direction`` compares the opportunity score with
#: a small tolerance so floating-point noise is not reported as a change; a
#: missing dimension on either side makes the delta ``None`` for that dimension
#: rather than being treated as zero.
DELTA_TOLERANCE = 1e-9


class TrustContractPendingError(OdiError):
    """A trust surface was reached without the inputs its convention needs.

    Raised instead of returning a fabricated value. ``capability`` is the
    surface that was reached and ``decision`` is the decision whose provisional
    convention could not be applied (usually because its inputs are absent).
    """

    def __init__(self, capability: str, decision: str) -> None:
        self.capability = capability
        self.decision = decision
        super().__init__(f"{capability} is not available until the {decision} decision is approved")


@dataclass(frozen=True)
class OpportunityInterval:
    """A band around an opportunity score, not a point.

    ``estimate`` marks a no-band placeholder (a single estimate), which the UI
    must treat as *no* band rather than a tight one. A zero-width survey band is
    a different state and is never proof of certainty.
    """

    outcome_id: str
    low: float
    high: float
    confidence_level: float
    n: int
    estimate: bool = False


@dataclass(frozen=True)
class OutcomeDelta:
    """The signed change between two accepted score states.

    ``importance``/``satisfaction``/``opportunity`` are the later minus the
    earlier value, or ``None`` when either side is missing that dimension.
    ``direction`` is the opportunity change signed as up/down/flat.
    """

    outcome_id: str
    importance: float | None
    satisfaction: float | None
    opportunity: float | None
    direction: DeltaDirection


@dataclass(frozen=True)
class RetainedSurveyInput:
    """The paired per-respondent inputs an interval is reproduced from (B3.1)."""

    outcome_id: str
    respondent_id: str
    importance: float
    satisfaction: float


@dataclass(frozen=True)
class IntervalProvenance:
    """Where a persisted band came from, and whether it is still valid (B3.2)."""

    outcome_id: str
    low: float
    high: float
    confidence_level: float
    n: int
    seed: int | None
    method: str
    computed_at: str
    stale: bool


def _paired_observations(outcome: Outcome) -> tuple[list[float], list[float]]:
    """The paired numeric observations a band is bootstrapped from.

    There is no per-respondent store wired to the outcome yet (B3.1 retention is
    a stub), so a survey outcome contributes its single accepted mean as one
    paired observation, which yields a zero-width band honestly labelled as a
    one-observation sample. A caller with real paired inputs should call
    :func:`agentic_odi_core.stats.opportunity_interval` directly.
    """
    if outcome.importance is None or outcome.satisfaction is None:
        return [], []
    return [outcome.importance], [outcome.satisfaction]


def opportunity_interval(outcome: Outcome) -> OpportunityInterval:
    """The percentile-bootstrap band for an outcome's score (B3).

    An outcome with a real sample gets a bootstrap band; an outcome whose score
    is a bare estimate gets a no-band placeholder (``low == high == score``,
    ``estimate=True``) that no consumer may present as measured precision.
    """
    if outcome.opportunity_score is None:
        raise TrustContractPendingError("opportunity_interval", BootstrapConvention)
    importance, satisfaction = _paired_observations(outcome)
    if not importance:
        raise TrustContractPendingError("opportunity_interval", BootstrapConvention)
    interval: Interval = _bootstrap_interval(
        importance,
        satisfaction,
        samples=DEFAULT_SAMPLES,
        seed=DEFAULT_SEED,
        confidence_level=DEFAULT_CONFIDENCE_LEVEL,
    )
    is_estimate = outcome.score_method == "estimate"
    return OpportunityInterval(
        outcome_id=outcome.id,
        low=interval.low,
        high=interval.high,
        confidence_level=interval.confidence_level,
        n=interval.n,
        estimate=is_estimate,
    )


def classify_confidence(outcome: Outcome) -> ConfidenceClass:
    """Classify how much evidence stands behind a score (B4.1).

    Uses the provisional table: measured at a sample of at least
    :data:`MEASURED_SAMPLE_THRESHOLD` from a survey or import; thin for a
    smaller survey/import sample; none for an estimate, an unknown count or no
    score. A survey method label alone is never treated as sufficient evidence.
    """
    if outcome.opportunity_score is None or outcome.score_method == "estimate":
        return "none"
    counts = [c for c in (outcome.importance_n, outcome.satisfaction_n) if c is not None]
    if not counts:
        return "none"
    # The weakest dimension bounds the class: a mean over 40 importance answers
    # and 2 satisfaction answers is not a measured pair.
    smallest = min(counts)
    return "measured" if smallest >= MEASURED_SAMPLE_THRESHOLD else "thin"


def parse_survey(rows: list[dict[str, object]]) -> list[SurveyResponse]:
    """Parse raw survey rows into responses (B2), per the import policy."""
    return _parse_survey(rows)


def aggregate_survey(
    inputs: list[SurveyResponse],
    *,
    id_by_statement: dict[str, str | None] | None = None,
    known_ids: set[str] | None = None,
) -> SurveyImportResult:
    """Aggregate responses into one mean per outcome (B2), per the import policy."""
    return _aggregate_survey(inputs, id_by_statement=id_by_statement, known_ids=known_ids)


#: B3.1 stub store. The retention/deletion and study-lineage policy is not yet
#: approved, so this keeps paired inputs for the process lifetime and never
#: deletes. It exists so the read side has a shape to call; a real store replaces
#: the dict without changing the function signatures.
_RETAINED_SURVEY_INPUTS: dict[str, list[RetainedSurveyInput]] = {}


def retain_survey_inputs(inputs: list[RetainedSurveyInput]) -> list[RetainedSurveyInput]:
    """Keep the paired inputs a band will later be recomputed from (B3.1).

    Stub: an in-memory, no-deletion store standing in for the unapproved
    retention policy. It returns the inputs it retained so a caller can confirm
    what is now reproducible.
    """
    for item in inputs:
        bucket = _RETAINED_SURVEY_INPUTS.setdefault(item.outcome_id, [])
        if not any(
            existing.respondent_id == item.respondent_id
            and existing.importance == item.importance
            and existing.satisfaction == item.satisfaction
            for existing in bucket
        ):
            bucket.append(item)
    return inputs


def retained_survey_inputs(outcome_id: str) -> list[RetainedSurveyInput]:
    """The paired inputs retained for an outcome (B3.1 stub read side).

    Refuses rather than returning an empty list when nothing was retained for
    the outcome: an empty list reads as "zero responses", which would let a
    caller bootstrap a band from no data instead of being told the input set is
    unavailable. That is exactly the unknown-turned-into-a-fact failure the
    retention decision must settle, so it stays a named refusal until the policy
    is approved.
    """
    bucket = _RETAINED_SURVEY_INPUTS.get(outcome_id)
    if not bucket:
        raise TrustContractPendingError("retained_survey_inputs", RetentionPolicy)
    return list(bucket)


def persisted_interval(
    outcome: Outcome, snapshots: list[ScoreSnapshot] | None = None
) -> IntervalProvenance:
    """Read a persisted band and its provenance, or refuse (B3.2).

    Reads ``opportunity_low``/``opportunity_high`` off the outcome. A band is
    stale when the latest accepted snapshot's score differs from the score the
    band was computed against, because an edit after the band was stored
    invalidates it rather than silently redefining it.
    """
    if outcome.opportunity_low is None or outcome.opportunity_high is None:
        raise TrustContractPendingError("persisted_interval", IntervalProvenancePolicy)
    computed_score = outcome.opportunity_score
    stale = False
    history = snapshots if snapshots is not None else []
    if history and computed_score is not None:
        latest = history[-1].opportunity_score
        stale = latest is not None and latest != computed_score
    return IntervalProvenance(
        outcome_id=outcome.id,
        low=outcome.opportunity_low,
        high=outcome.opportunity_high,
        confidence_level=outcome.interval_confidence_level or DEFAULT_CONFIDENCE_LEVEL,
        n=outcome.interval_n or 0,
        seed=outcome.interval_seed,
        method=outcome.score_method,
        computed_at=outcome.interval_computed_at or "",
        stale=stale,
    )


def rank_outcomes_honestly(outcomes: list[Outcome]) -> list[Outcome]:
    """Rank outcomes without mixing unknown scores into zeroes (B4).

    Groups by confidence class -- measured first, then thin, then none -- and
    orders within a group by the low end of the band (falling back to the point
    score when no band is stored) descending, then by outcome id for a stable
    tie-break. An unscored outcome stays in the ``none`` group, never sorted as
    a zero.
    """
    order = {"measured": 0, "thin": 1, "none": 2}

    def sort_key(outcome: Outcome) -> tuple[int, float, str]:
        band_low = outcome.opportunity_low
        basis = band_low if band_low is not None else (outcome.opportunity_score or 0.0)
        return (order[classify_confidence(outcome)], -basis, outcome.id)

    return sorted(outcomes, key=sort_key)


def outcome_delta(snapshots: list[ScoreSnapshot], since: str | None = None) -> OutcomeDelta:
    """The signed change from a baseline snapshot to the latest (B6.1).

    Baseline selection (provisional): with ``since`` given, the baseline is the
    last snapshot at or before that ISO-8601 timestamp; a ``since`` before the
    first snapshot is an error, not a zero baseline. With ``since`` omitted, the
    baseline is the earliest snapshot. A missing dimension on either side yields
    ``None`` for that dimension. An empty history is an error.
    """
    if not snapshots:
        raise ValidationError("no score history to compare; there is no baseline")
    ordered = sorted(snapshots, key=lambda snapshot: snapshot.at)
    baseline = ordered[0]
    if since is not None:
        candidates = [snapshot for snapshot in ordered if snapshot.at <= since]
        if not candidates:
            raise ValidationError(
                f"since={since!r} is before the first snapshot; there is no baseline"
            )
        baseline = candidates[-1]
    latest = ordered[-1]

    def _diff(after: float | None, before: float | None) -> float | None:
        if after is None or before is None:
            return None
        return after - before

    importance = _diff(latest.importance, baseline.importance)
    satisfaction = _diff(latest.satisfaction, baseline.satisfaction)
    opportunity = _diff(latest.opportunity_score, baseline.opportunity_score)
    if opportunity is None or abs(opportunity) <= DELTA_TOLERANCE:
        direction: DeltaDirection = "flat"
    else:
        direction = "up" if opportunity > 0 else "down"
    return OutcomeDelta(
        outcome_id=latest.outcome_id,
        importance=importance,
        satisfaction=satisfaction,
        opportunity=opportunity,
        direction=direction,
    )


def opportunity_delta_from_scores(
    before: float | None, after: float | None
) -> tuple[float | None, DeltaDirection]:
    """Sign a bare opportunity change with the same tolerance rule (B6.1).

    The existing score function is reused for the *values*; this only decides the
    direction, so the CLI, the API and the store cannot disagree about what
    "up" means.
    """
    if before is None or after is None:
        return None, "flat"
    change = after - before
    if abs(change) <= DELTA_TOLERANCE:
        return change, "flat"
    return change, "up" if change > 0 else "down"


__all__ = [
    "BootstrapConvention",
    "ConfidenceClass",
    "ConfidenceTable",
    "DELTA_TOLERANCE",
    "DeltaDirection",
    "DeltaSemantics",
    "ImportPolicy",
    "IntervalProvenance",
    "IntervalProvenancePolicy",
    "MEASURED_SAMPLE_THRESHOLD",
    "OpportunityInterval",
    "OutcomeDelta",
    "RetainedSurveyInput",
    "RetentionPolicy",
    "SurveyAggregate",
    "TrustContractPendingError",
    "aggregate_survey",
    "classify_confidence",
    "opportunity_delta_from_scores",
    "opportunity_interval",
    "outcome_delta",
    "parse_survey",
    "persisted_interval",
    "rank_outcomes_honestly",
    "retain_survey_inputs",
    "retained_survey_inputs",
]
