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


class Outcome(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The ID of the Job this outcome relates to")
    step_id: str | None = Field(None, description="The ID of the specific Step, if applicable")
    study_id: str | None = Field(
        None, description="The study wave this measurement belongs to, when it is one"
    )
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
    quote_id: str | None = Field(
        default=None, description="The Evidence record this outcome was promoted from"
    )
    customer_value: CustomerValue
    business_value: BusinessValue

    @computed_field
    @property
    def opportunity_score(self) -> float:
        return self.customer_value.opportunity_score


class SegmentVerdict(str, Enum):
    """Stage 5's verdict on a group of people, computed from their outcomes."""

    UNDERSERVED = "underserved"
    OVERSERVED = "overserved"
    APPROPRIATELY_SERVED = "appropriately_served"


class StrategyKind(str, Enum):
    """Stage 6's three strategic paths."""

    DIFFERENTIATED = "differentiated"
    DISRUPTIVE = "disruptive"
    NEW_MARKET = "new_market"


class Segment(BaseModel):
    """A group of people plus the functional job they are trying to do.

    The unit of analysis is the outcome: ``outcome_ids`` is the evidence, and
    ``verdict`` is derived from it, never typed in. ``verdict`` is ``None`` when
    an outcome in the group has no score, because a segment cannot be classified
    from partial evidence. No demographic attribute appears here by design.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str | None = Field(None, description="The Job this segment is scoped to")
    name: str = Field(..., description='Human label, e.g. "Platform engineers, secrets rotation"')
    people: str = Field(..., description="The group, in the person's words when they are recorded")
    people_inferred: bool = Field(
        False,
        description="True when `people` was derived from the outcomes, not supplied",
    )
    job_statement: str = Field(..., description="The functional job in their words")
    outcome_ids: list[str] = Field(
        default_factory=list, description="The evidence for this segment"
    )
    verdict: SegmentVerdict | None = Field(
        None, description="Derived from the outcomes; None means not enough signal"
    )
    rationale: str = Field(..., description="Why this verdict, naming the outcomes behind it")
    confidence: float = Field(..., ge=0.0, le=1.0, description="How much evidence supports this")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Strategy(BaseModel):
    """One recommended innovation path, with the paths it beat recorded.

    A strategy without its rejections is a conclusion, not a recommendation, so
    ``rejected`` carries one entry for every kind that was not chosen.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: StrategyKind
    segment_id: str | None = Field(None, description="The segment this bet is aimed at")
    thesis: str = Field(..., description="One paragraph: why this path, from the evidence")
    bets: list[str] = Field(default_factory=list, description="The proposed moves")
    rejected: list[dict[str, Any]] = Field(
        default_factory=list, description='[{"kind": "disruptive", "why": "..."}]'
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SignalKind(str, Enum):
    """The facts a signal may report. Every kind here has a real producer."""

    OUTCOME_SCORED = "outcome_scored"
    OPPORTUNITY_CROSSED = "opportunity_crossed"
    EVIDENCE_INGESTED = "evidence_ingested"
    EVIDENCE_PROMOTED = "evidence_promoted"
    JOB_ADDED = "job_added"
    JOB_MAP_COMPLETED = "job_map_completed"
    SEGMENT_IDENTIFIED = "segment_identified"
    STRATEGY_PROPOSED = "strategy_proposed"


SignalSeverity = Literal["info", "notice", "urgent"]


class Signal(BaseModel):
    """One fact that happened in the store, surfaced in the Catch Up feed."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: SignalKind
    title: str = Field(..., max_length=120, description="One line, at most 120 characters")
    detail: str | None = None
    subject_kind: (
        Literal[
            "job", "step", "outcome", "evidence", "connector", "agent_work", "segment", "strategy"
        ]
        | None
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


class StudyStatus(str, Enum):
    """Whether a wave is still taking measurements."""

    OPEN = "open"
    CLOSED = "closed"


class StudyGuide(BaseModel):
    """The interview guide a wave uses, held by value so the wave is reproducible.

    A version string travels with the questions: two waves may deliberately use
    different guides, and the comparison must be able to say so.
    """

    name: str = Field(..., description="The guide's label, e.g. 'Corn growers, core interview'")
    version: str = Field("1", description="Version of this guide")
    questions: list[str] = Field(default_factory=list, description="The questions, in order")


class StudyFrame(BaseModel):
    """What carries between waves: the guide, the outcome statements, the themes.

    Stored by value on the wave, never as a pointer into a job-level record.
    Editing a copied frame must not mutate its source, and a frame must survive
    the source being changed or removed, so a wave can always be reproduced.
    """

    guide: StudyGuide | None = Field(None, description="The interview guide this wave used")
    outcome_statements: list[str] = Field(
        default_factory=list, description="The outcome statements this wave set out to measure"
    )
    themes: list[str] = Field(
        default_factory=list, description="The themes the frame groups statements under"
    )


class Study(BaseModel):
    """One wave of a study: a job, measured at one point in time.

    A study is what makes "the market last quarter" and "the market this
    quarter" comparable. The *frame* — the guide, the outcome statements, the
    themes — carries between waves; the measurements do not, because a wave
    starts unmeasured. ``lineage_id`` groups a wave with its siblings: wave 1
    has ``lineage_id == id``, and ``next_wave`` stamps the same lineage on the
    clone. Measurements live on :class:`Outcome`, linked back by ``study_id``.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lineage_id: str = Field(..., description="Groups the waves of one study; wave 1 is its own")
    job_id: str = Field(..., description="The Job this study measures")
    name: str = Field(..., description='Human label, e.g. "Corn growers, quarterly pulse"')
    wave: int = Field(1, ge=1, description="1-based wave number inside this lineage")
    status: StudyStatus = Field(StudyStatus.OPEN, description="Whether the wave is still measuring")
    frame: StudyFrame = Field(default_factory=StudyFrame, description="The wave's carried frame")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OutcomeComparisonStatus(str, Enum):
    """How one statement changed between two waves."""

    MOVED = "moved"
    STABLE = "stable"
    ADDED = "added"
    DROPPED = "dropped"
    UNMEASURED = "unmeasured"


class OutcomeComparison(BaseModel):
    """One statement's two measurements, side by side.

    A missing score stays ``None``: an absent measurement is not a zero, and
    rendering it as one would make every added statement look like a collapse.
    """

    statement: str
    score_a: float | None = Field(None, description="Mean score in wave A, or None if unmeasured")
    score_b: float | None = Field(None, description="Mean score in wave B, or None if unmeasured")
    delta: float | None = Field(None, description="score_b - score_a, only when both are scored")
    n_a: int = Field(0, description="Measurements of this statement in wave A")
    n_b: int = Field(0, description="Measurements of this statement in wave B")
    status: OutcomeComparisonStatus


class WaveComparison(BaseModel):
    """Two waves compared statement by statement, never by outcome id.

    Keyed by statement so an outcome re-created in the second wave still lines
    up with its twin in the first.
    """

    study_a: str = Field(..., description="The earlier wave's id")
    study_b: str = Field(..., description="The later wave's id")
    job_id: str = Field(..., description="The job both waves measure")
    per_outcome: list[OutcomeComparison] = Field(default_factory=list)
    added: list[str] = Field(default_factory=list, description="Statements only in wave B")
    dropped: list[str] = Field(default_factory=list, description="Statements only in wave A")
    stable: list[str] = Field(default_factory=list, description="Statements unchanged in both")
