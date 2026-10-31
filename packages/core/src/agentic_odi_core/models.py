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

JOB_STAGE_DESCRIPTIONS: dict[JobStage, str] = {
    JobStage.DEFINE: "Determine goals and criteria",
    JobStage.LOCATE: "Gather inputs and resources",
    JobStage.PREPARE: "Set up context and workspace",
    JobStage.CONFIRM: "Verify readiness to execute",
    JobStage.EXECUTE: "Carry out core job work",
    JobStage.MONITOR: "Track performance and errors",
    JobStage.MODIFY: "Adjust inputs or workflows",
    JobStage.CONCLUDE: "Finish and store outputs",
}


def job_stage_catalog() -> list[dict[str, str]]:
    """The eight Universal Job Map stages as display data.

    ``apps/studio/src/domain/jobStages.ts`` is generated from this function
    (``scripts/gen_job_stages.py``); a contract test fails if the two drift.
    """
    return [
        {
            "id": stage.value,
            "name": f"{index}. {stage.value.capitalize()}",
            "desc": JOB_STAGE_DESCRIPTIONS[stage],
        }
        for index, stage in enumerate(JOB_STAGE_ORDER, start=1)
    ]


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

JOB_NAME_PATTERN = r"^[A-Za-z0-9 _-]+$"
JOB_NAME_MIN_LENGTH = 3
JOB_NAME_MAX_LENGTH = 64
JOB_DESCRIPTION_MAX_LENGTH = 500


class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(
        ...,
        min_length=JOB_NAME_MIN_LENGTH,
        max_length=JOB_NAME_MAX_LENGTH,
        pattern=JOB_NAME_PATTERN,
        description="The name of the Job-to-be-Done",
    )
    description: str | None = Field(
        None,
        max_length=JOB_DESCRIPTION_MAX_LENGTH,
        description="Detailed description of the Job",
    )
    origin: Origin = Field("user", description="Where this row came from")


def create_job(name: str, description: str | None = None) -> Job:
    """Build a Job through model validation before it reaches a repository."""
    return Job(name=name, description=description)


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


class SignalKind(str, Enum):
    """The facts a signal may report. Every kind here has a real producer."""

    OUTCOME_SCORED = "outcome_scored"
    OPPORTUNITY_CROSSED = "opportunity_crossed"
    EVIDENCE_INGESTED = "evidence_ingested"
    EVIDENCE_PROMOTED = "evidence_promoted"
    JOB_ADDED = "job_added"
    JOB_MAP_COMPLETED = "job_map_completed"


SignalSeverity = Literal["info", "notice", "urgent"]


class Signal(BaseModel):
    """One fact that happened in the store, surfaced in the Catch Up feed."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: SignalKind
    title: str = Field(..., max_length=120, description="One line, at most 120 characters")
    detail: str | None = None
    subject_kind: (
        Literal["job", "step", "outcome", "evidence", "connector", "agent_work"] | None
    ) = None
    subject_id: str | None = None
    severity: SignalSeverity = "info"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    read_at: datetime | None = None
    dismissed_at: datetime | None = None
    #: True when the attention budget withheld this signal from the feed.
    suppressed: bool = False
    fingerprint: str = Field(
        ..., description="sha256 of kind|subject_kind|subject_id|discriminator"
    )


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
