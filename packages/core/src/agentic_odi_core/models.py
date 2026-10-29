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


class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="The name of the Job-to-be-Done")
    description: str | None = Field(None, description="Detailed description of the Job")


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


class DecisionConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Rejection(BaseModel):
    """An option a decision considered and rejected, with its reason.

    The reason is required and non-empty: a rejection without a reason cannot be
    steelmanned later, and keeping the rejected options is the point.
    """

    outcome_id: str = Field(..., description="The rejected Outcome's ID")
    reason: str = Field(..., min_length=1, description="Why this option was not chosen")


class Decision(BaseModel):
    """A recorded choice: what was chosen, what was rejected, and why.

    A newer decision supersedes an older one rather than overwriting it, so the
    argument that was lost stays readable. ``superseded_at``/``superseded_by``
    are set on the predecessor when a successor is recorded.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The Job this decision belongs to")
    chosen_outcome_ids: list[str] = Field(
        ..., min_length=1, description="Outcome IDs the decision chose"
    )
    rejected: list[Rejection] = Field(default_factory=list)
    rationale: str = Field(..., min_length=1, description="Why this choice was made")
    decided_by: str = Field(
        ..., min_length=1, description="Who recorded the decision (attribution, not authentication)"
    )
    decided_at: str = Field(..., description="ISO-8601 timestamp, supplied at write time")
    confidence: DecisionConfidence = Field(DecisionConfidence.MEDIUM)
    superseded_at: str | None = Field(None, description="When a later decision replaced this one")
    superseded_by: str | None = Field(
        None, description="The ID of the decision that replaced this one"
    )
