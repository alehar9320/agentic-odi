"""Core domain models for Agentic ODI."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
    source_kind: str = Field(
        ..., description="Connector kind, e.g. mcp, rest, webhook, manual — or demo for a fixture"
    )
    item_type: EvidenceItemType = Field(
        "manual", description="Normalized record kind produced by the connector"
    )
    name: str = Field(..., description="Short human-readable label for the record")
    content: str = Field(..., description="Normalized text content of the record")
    url: str | None = Field(
        None, description="External URL/link to the signal/evidence in the source system"
    )
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


class V2MOM(BaseModel):
    """The domain's V2MOM artifact: Vision, Values, Methods, Obstacles, Measures.

    Only ``vision`` has an input path today, in the Studio's context
    conversation. Nothing extracts the other four from a conversation and no
    surface captures them, so a V2MOM in practice is its vision and four empty
    lists.
    """

    vision: str = Field("", description="What you want to achieve or create")
    values: list[str] = Field(
        default_factory=list, description="Principles and beliefs that guide decisions"
    )
    methods: list[str] = Field(
        default_factory=list, description="Actions and strategies to achieve the vision"
    )
    obstacles: list[str] = Field(
        default_factory=list, description="Challenges and risks that stand in the way"
    )
    measures: list[str] = Field(
        default_factory=list, description="Metrics and key results that measure success"
    )


class ScheduledWorkStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledWorkTriggerType(str, Enum):
    ONESHOT = "oneshot"
    CRON = "cron"
    INTERVAL = "interval"


class ScheduledWork(BaseModel):
    """A scheduled task or agent run in the cloud."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Name or title of the scheduled work task")
    agent_id: str = Field(
        "default-agent", description="ID/alias of the agent assigned to run the work"
    )
    trigger_type: ScheduledWorkTriggerType = Field(
        ScheduledWorkTriggerType.ONESHOT, description="Trigger mechanism (oneshot, cron, interval)"
    )
    schedule_expression: str = Field(
        ...,
        description="ISO timestamp, relative delay, or cron expression (e.g. '0 * * * *' or '+1h')",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Parameters or prompt for the cloud task"
    )
    status: ScheduledWorkStatus = Field(
        ScheduledWorkStatus.SCHEDULED, description="Current status of the task"
    )
    job_id: str | None = Field(None, description="Associated ODI Job ID, if any")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_run_at: str | None = Field(None, description="ISO timestamp of last execution")
    next_run_at: str | None = Field(None, description="ISO timestamp of next scheduled execution")
    result_summary: str | None = Field(None, description="Execution outcome or error summary")
