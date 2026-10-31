"""Core domain models for Agentic ODI."""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, model_validator


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


class SignalKind(str, Enum):
    """The facts a signal may report. Every kind here has a real producer.

    The ``know`` kinds (``bet_due``, ``decision_superseded``, ``coverage_gap``)
    are recorded by the Pillar 4 emission pass; ``score_moved`` is the know
    view of a re-scored outcome and maps to the same write path as
    ``outcome_scored``.
    """

    OUTCOME_SCORED = "outcome_scored"
    OPPORTUNITY_CROSSED = "opportunity_crossed"
    EVIDENCE_INGESTED = "evidence_ingested"
    EVIDENCE_PROMOTED = "evidence_promoted"
    JOB_ADDED = "job_added"
    JOB_MAP_COMPLETED = "job_map_completed"
    BET_DUE = "bet_due"
    SCORE_MOVED = "score_moved"
    DECISION_SUPERSEDED = "decision_superseded"
    COVERAGE_GAP = "coverage_gap"


SignalSeverity = Literal["info", "notice", "urgent"]


class Signal(BaseModel):
    """One fact that happened in the store, surfaced in the Catch Up feed."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: SignalKind
    title: str = Field(..., max_length=120, description="One line, at most 120 characters")
    detail: str | None = None
    subject_kind: (
        Literal[
            "job",
            "step",
            "outcome",
            "evidence",
            "connector",
            "agent_work",
            "bet",
            "decision",
            "job_stage",
        ]
        | None
    ) = None
    subject_id: str | None = None
    #: The Job this fact belongs to, for scoping a feed or digest to one job.
    #: ``None`` only for a fact that genuinely has no job yet.
    job_id: str | None = None
    severity: SignalSeverity = "info"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    read_at: datetime | None = None
    dismissed_at: datetime | None = None
    #: True when the attention budget withheld this signal from the feed.
    suppressed: bool = False
    #: The proven numeric delta for ``score_moved``; ``None`` for other kinds.
    #: Typed so a notification rule never has to parse the summary text.
    magnitude: float | None = None
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


class DecisionConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RejectedOutcome(BaseModel):
    """An alternative that was considered and turned down, with the reason."""

    outcome_id: str = Field(..., description="The Outcome that was not chosen")
    reason: str = Field(..., min_length=1, description="Why it was rejected (non-empty)")


class Decision(BaseModel):
    """A recorded choice: what was chosen, what was rejected, and why.

    Decisions are event-sourced and superseded rather than overwritten, so the
    reasoning outlives the meeting. ``superseded_at``/``superseded_by`` are set
    when a later decision for the same job replaces this one; the row stays
    readable.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The Job this decision belongs to")
    chosen_outcome_ids: list[str] = Field(
        default_factory=list, description="Outcomes that were chosen"
    )
    rejected: list[RejectedOutcome] = Field(
        default_factory=list, description="Outcomes that were rejected, each with a reason"
    )
    rationale: str = Field(..., min_length=1, description="Why this choice was made")
    decided_by: str = Field(..., min_length=1, description="Free-text actor recorded at write time")
    decided_at: datetime = Field(..., description="When the decision was made")
    confidence: DecisionConfidence = Field(
        DecisionConfidence.MEDIUM, description="How confident the decision was"
    )
    superseded_at: datetime | None = Field(
        None, description="When a later decision replaced this one"
    )
    superseded_by: str | None = Field(None, description="The Decision ID that replaced this one")


class ScoreSnapshot(BaseModel):
    """An append-only record of an accepted score, with its evidence state.

    A history of bare numbers cannot answer "did the evidence change or the
    estimate?". The snapshot stores the score *and* its sample counts and
    method so a delta can be read honestly.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    outcome_id: str = Field(..., description="The Outcome this score belongs to")
    job_id: str = Field(..., description="The Job the outcome belongs to, for scoping")
    at: datetime = Field(..., description="When this score was accepted")
    importance: float = Field(..., ge=1.0, le=10.0)
    satisfaction: float = Field(..., ge=1.0, le=10.0)
    importance_n: int | None = Field(
        None, description="How many people the importance estimate came from"
    )
    satisfaction_n: int | None = Field(
        None, description="How many people the satisfaction estimate came from"
    )
    method: str | None = Field(
        None, description="How the score was obtained, e.g. survey, estimate"
    )
    note: str | None = Field(None, max_length=500, description="Optional reason for the score")

    @computed_field
    @property
    def opportunity_score(self) -> float:
        return compute_opportunity_score(self.importance, self.satisfaction)


class BetStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    MEASURED = "measured"
    ABANDONED = "abandoned"


#: Legal bet status transitions. ``measured`` and ``abandoned`` are terminal.
BET_TRANSITIONS: dict[BetStatus, tuple[BetStatus, ...]] = {
    BetStatus.PLANNED: (BetStatus.RUNNING, BetStatus.ABANDONED),
    BetStatus.RUNNING: (BetStatus.MEASURED,),
    BetStatus.MEASURED: (),
    BetStatus.ABANDONED: (),
}


#: The metrics a disproof condition may observe. These are the proven numbers
#: a bet's own outcome already carries, so a condition never invents a scale.
DISPROOF_METRICS: tuple[str, ...] = (
    "opportunity",
    "importance",
    "satisfaction",
)


class DisproofOperator(str, Enum):
    """How an observed value is compared against a condition's threshold."""

    BELOW = "below"
    ABOVE = "above"
    AT_OR_BELOW = "at_or_below"
    AT_OR_ABOVE = "at_or_above"


class DisproofCondition(BaseModel):
    """A falsification condition committed before a bet runs.

    A condition names the metric, the comparison and the value that would
    prove the bet wrong, plus the day by which it must be judged. Storing it as
    typed fields (not prose) is what lets ``evaluate_disproof`` return a verdict
    instead of an opinion.
    """

    metric: str = Field(..., description="opportunity, importance or satisfaction")
    operator: DisproofOperator = Field(..., description="How the metric is compared")
    threshold: float = Field(..., description="The value the metric is compared against")
    by_date: date = Field(..., description="The day by which this must be judged")
    rationale: str = Field(..., min_length=1, description="Why this would disprove the bet")

    @model_validator(mode="after")
    def _validate(self) -> DisproofCondition:
        if self.metric not in DISPROOF_METRICS:
            allowed = ", ".join(DISPROOF_METRICS)
            raise ValueError(
                f"unsupported disproof metric '{self.metric}'; choose one of {allowed}"
            )
        if not math.isfinite(self.threshold):
            raise ValueError("disproof threshold must be a finite number")
        if not self.rationale.strip():
            raise ValueError("disproof condition needs a rationale")
        return self


class Bet(BaseModel):
    """A decision-linked expectation with a frozen baseline.

    ``baseline`` is the outcome's opportunity score captured at creation and
    stored, never recomputed: the whole point of a bet is that its starting
    point cannot drift with later scores. ``direction`` names which way the
    canonical metric must move for the bet to be met.

    ``disproof`` holds the conditions committed before the bet runs. A bet may
    be created ``planned`` with none, but it cannot move to ``running`` without
    at least one — a bet that can run without a falsifier is a wish.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = Field(..., description="The Decision this bet follows from")
    outcome_id: str = Field(..., description="The Outcome this bet targets")
    job_id: str = Field(..., description="The Job the outcome belongs to")
    hypothesis: str = Field(..., min_length=1, description="What you expect to happen")
    baseline: float = Field(..., description="The canonical metric captured at creation (frozen)")
    target: float = Field(..., description="The value the metric must reach to be met")
    measure_by: date = Field(..., description="The day you will look")
    direction: Direction = Field(
        Direction.MAXIMIZE,
        description="Whether a higher (maximize) or lower (minimize) metric value is success",
    )
    status: BetStatus = Field(BetStatus.PLANNED, description="Lifecycle state")
    measured_at: datetime | None = Field(None, description="When the bet was measured")
    created_at: datetime = Field(..., description="When the bet was created")
    disproof: list[DisproofCondition] = Field(
        default_factory=list,
        description="Conditions committed before the bet runs; required to start it",
    )
    baseline_snapshot_id: str | None = Field(
        None, description="The ScoreSnapshot the baseline was read from, for provenance"
    )
    baseline_importance: float | None = Field(
        None, description="The outcome's importance when the baseline was captured"
    )
    baseline_satisfaction: float | None = Field(
        None, description="The outcome's satisfaction when the baseline was captured"
    )


class BetMeasurementResult(str, Enum):
    MET = "met"
    MISSED = "missed"
    NO_DATA = "no_data"


class NotificationRule(BaseModel):
    """One stored interruption rule per supported kind."""

    kind: SignalKind = Field(..., description="The signal kind this rule governs")
    threshold: float = Field(
        0.0, description="For score_moved, the minimum |delta| that may interrupt"
    )
    enabled: bool = Field(True, description="Whether this kind may interrupt at all")
