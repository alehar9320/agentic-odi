"""Core domain models for Agentic ODI."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field


class Direction(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class JobStage(str, Enum):
    """Ulwick's Universal Job Map stages, in canonical order."""

    DEFINE = "define"
    LOCATE = "locate"
    PREPARE = "prepare"
    CONFIRM = "confirm"
    EXECUTE = "execute"
    MONITOR = "monitor"
    MODIFY = "modify"
    CONCLUDE = "conclude"


JOB_STAGE_ORDER: list[JobStage] = [
    JobStage.DEFINE,
    JobStage.LOCATE,
    JobStage.PREPARE,
    JobStage.CONFIRM,
    JobStage.EXECUTE,
    JobStage.MONITOR,
    JobStage.MODIFY,
    JobStage.CONCLUDE,
]

JOB_STAGE_INDEX: dict[JobStage, int] = {
    stage: index + 1 for index, stage in enumerate(JOB_STAGE_ORDER)
}


class BusinessImpactCategory(str, Enum):
    REVENUE_GROWTH = "revenue_growth"
    COST_REDUCTION = "cost_reduction"
    RETENTION = "retention"
    RISK_MITIGATION = "risk_mitigation"
    OPERATIONAL_EFFICIENCY = "operational_efficiency"
    COMPLIANCE = "compliance"
    BRAND_REPUTATION = "brand_reputation"
    OTHER = "other"


def compute_opportunity_score(importance: float, satisfaction: float) -> float:
    """ODI Opportunity Score = importance + max(importance - satisfaction, 0)."""
    return float(importance + max(importance - satisfaction, 0.0))


#: Where a row came from. ``user`` is a row a person entered; ``demo`` is the
#: deliberate sample workspace; ``sample`` is the site sample; ``imported`` is
#: an imported record. One vocabulary serves the demo loader, the site sample
#: and imports, so a sample row is never mistaken for the user's own data.
Origin = Literal["user", "demo", "sample", "imported"]


class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="The name of the Job-to-be-Done")
    description: str | None = Field(None, description="Detailed description of the Job")
    origin: Origin = Field("user", description="Where this row came from")


class Step(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The ID of the Job this step belongs to")
    name: str = Field(..., description="The name of the job step")
    order: int = Field(..., description="The chronological order of this step in the job map")
    stage: JobStage | None = Field(
        None, description="The Universal Job Map stage this step belongs to"
    )
    stage_index: int | None = Field(
        None, ge=1, le=8, description="Position (1-8) in the canonical stage order"
    )
    origin: Origin = Field("user", description="Where this row came from")


class Outcome(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The ID of the Job this outcome relates to")
    step_id: str | None = Field(None, description="The ID of the specific Step, if applicable")
    statement: str = Field(
        ..., description="The desired outcome statement (e.g., 'Minimize the time it takes to...')"
    )
    importance: float | None = Field(
        default=None, ge=1.0, le=10.0, description="Importance score (1-10)"
    )
    satisfaction: float | None = Field(
        default=None, ge=1.0, le=10.0, description="Current satisfaction score (1-10)"
    )
    opportunity_score: float | None = Field(
        None, description="Opportunity score (Importance + max(Importance - Satisfaction, 0))"
    )
    origin: Origin = Field("user", description="Where this row came from")


class ValueMetric(BaseModel):
    name: str
    direction: Direction
    unit_of_measure: str
    importance: float = Field(ge=1.0, le=10.0)
    satisfaction: float = Field(ge=1.0, le=10.0)

    @computed_field
    @property
    def opportunity_score(self) -> float:
        return compute_opportunity_score(self.importance, self.satisfaction)


class CustomerValue(BaseModel):
    direction: Direction
    unit_of_measure: str
    object_of_control: str
    contextual_clarifier: str | None = None
    statement: str
    importance: float = Field(ge=1.0, le=10.0)
    satisfaction: float = Field(ge=1.0, le=10.0)
    value_metrics: list[ValueMetric] = Field(default_factory=list)

    @computed_field
    @property
    def opportunity_score(self) -> float:
        return compute_opportunity_score(self.importance, self.satisfaction)


class BusinessValue(BaseModel):
    category: BusinessImpactCategory
    statement: str
    detail: str | None = None
    estimated_annual_value: float | None = Field(default=None, ge=0.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


EvidenceItemType = Literal["catalog", "resource", "tool_result", "manual", "note"]


class Evidence(BaseModel):
    """A captured research record linked (optionally) to ODI artifacts."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str = Field(..., description="Connector or person that produced the record")
    source_kind: str = Field(..., description="Connector kind, e.g. mcp, rest, webhook, manual")
    item_type: EvidenceItemType = Field(
        "manual", description="Normalized record kind produced by the connector"
    )
    name: str = Field(..., description="Short human-readable label for the record")
    content: str = Field(..., description="Normalized text content of the record")
    raw: dict[str, Any] = Field(default_factory=dict, description="Original record payload")
    job_id: str | None = Field(None, description="Job this evidence supports")
    step_id: str | None = Field(None, description="Job-map Step this evidence supports")
    outcome_id: str | None = Field(None, description="Desired Outcome this evidence supports")
    origin: Origin = Field("user", description="Where this row came from")


class CustomerOutcome(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The ID of the Job this outcome relates to")
    step_id: str | None = Field(
        default=None, description="The ID of the specific Step, if applicable"
    )
    customer_value: CustomerValue
    business_value: BusinessValue

    @computed_field
    @property
    def opportunity_score(self) -> float:
        return self.customer_value.opportunity_score


class CandidateStatus(str, Enum):
    """Where a proposed outcome sits in the review state machine.

    ``PROPOSED`` awaits a person; ``ACCEPTED`` became a real :class:`Outcome`;
    ``REJECTED`` was declined (with a reason); ``MERGED`` folded into an existing
    outcome. Rejection and merge are kept, never deleted — they are information
    about the extractor.
    """

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MERGED = "merged"


class OutcomeCandidate(BaseModel):
    """A proposed outcome extracted from a quote — a proposal, never an Outcome.

    A candidate is what the machine suggests; a person accepts, edits, merges or
    rejects it. Extraction never writes to ``outcomes``. ``status`` records the
    human's decision, and ``outcome_id`` links the outcome an acceptance created
    (``merged_into`` links the outcome a merge folded into).

    ``interview_id``/``quote_id`` reference the interview record owned by ``A1``
    (``ALH-14``) by id, the same way :class:`Evidence` references a job by id
    rather than owning it.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    quote_id: str = Field(..., description="The source quote this candidate came from")
    statement: str = Field(..., description="The proposed ODI desired-outcome statement")
    rationale: str = Field(
        "", description="Why the extractor proposed it, or the validator's reason when rejected"
    )
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Extractor confidence, displayed not thresholded"
    )
    status: CandidateStatus = Field(
        CandidateStatus.PROPOSED, description="Where this candidate sits in review"
    )
    interview_id: str | None = Field(None, description="The interview record, if known")
    job_id: str | None = Field(
        None, description="The Job this candidate would become an outcome of"
    )
    step_id: str | None = Field(None, description="The Step this candidate would attach to")
    outcome_id: str | None = Field(
        None, description="The Outcome an acceptance created, or a merge folded into"
    )
    merged_into: str | None = Field(
        None, description="The existing Outcome a merge folded this candidate into"
    )
    rejection_reason: str | None = Field(
        None, description="Why a person rejected this candidate; required to reject"
    )


class DecisionRecord(BaseModel):
    """A recorded decision about a subject (typically an accepted outcome).

    Persisted so the loop can be replayed: a decision names what was chosen and
    why, and is the parent of the :class:`BetRecord` that tests it.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject_id: str = Field(..., description="The Outcome this decision is about")
    choice: str = Field(..., description="What was chosen")
    rationale: str = Field(..., description="Why it was chosen")
    decided_at: str = Field(..., description="ISO-8601 timestamp of the decision")


class BetRecord(BaseModel):
    """A bet: a decision's claim, plus the metric that would move if it is right.

    ``baseline`` is ``None`` when the metric has not been measured yet — an
    unknown baseline, not a measured zero.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = Field(..., description="The Decision this bet tests")
    statement: str = Field(..., description="The claim being bet on")
    metric: str = Field(..., description="The metric that would move")
    baseline: float | None = Field(
        default=None, description="The metric's value before the bet, if known"
    )


class MeasurementRecord(BaseModel):
    """What a bet measured, against its baseline.

    ``value`` may be ``None``: a measurement that has not been taken is
    representable without inventing a number.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bet_id: str = Field(..., description="The Bet this measurement belongs to")
    metric: str = Field(..., description="The metric that was measured")
    value: float | None = Field(default=None, description="The measured value, if taken")
    observed_at: str = Field(..., description="ISO-8601 timestamp of the observation")
