"""Core domain models for Agentic ODI."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
ScoreMethod = Literal["estimate", "survey", "import"]

SCORE_SNAPSHOT_NOTE_MAX = 500


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string.

    One helper so every snapshot timestamp shares a format and timezone.
    """
    return datetime.now(timezone.utc).isoformat()


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
    importance_n: int | None = Field(
        default=None, ge=1, description="People behind the importance score, when known"
    )
    satisfaction_n: int | None = Field(
        default=None, ge=1, description="People behind the satisfaction score, when known"
    )
    score_method: ScoreMethod = Field(
        default="estimate",
        description="How the score was obtained: a one-person estimate, a survey, or an import",
    )
    opportunity_low: float | None = Field(
        None, description="Low end of the score band, when a band was computed (B3)"
    )
    opportunity_high: float | None = Field(
        None, description="High end of the score band, when a band was computed (B3)"
    )
    interval_n: int | None = Field(
        None, ge=1, description="Observations the band was computed from (B3)"
    )
    interval_seed: int | None = Field(None, description="Seed that reproduces the band (B3)")
    interval_confidence_level: float | None = Field(
        None, description="Confidence level of the band, e.g. 0.95 (B3)"
    )
    interval_computed_at: str | None = Field(
        None, description="When the band was computed, for staleness (B3.2)"
    )

    @model_validator(mode="after")
    def _count_requires_a_sample(self) -> Outcome:
        # A count above one means people were asked; an estimate cannot have asked them.
        if self.score_method == "estimate" and (
            (self.importance_n or 0) > 1 or (self.satisfaction_n or 0) > 1
        ):
            raise ValueError(
                "score_method 'estimate' cannot carry a sample count above 1; "
                "use 'survey' or 'import' when people were asked"
            )
        if (self.opportunity_low is None) != (self.opportunity_high is None):
            raise ValueError("a band needs both opportunity_low and opportunity_high")
        if (
            self.opportunity_low is not None
            and self.opportunity_high is not None
            and self.opportunity_low > self.opportunity_high
        ):
            raise ValueError("opportunity_low cannot exceed opportunity_high")
        # Provenance describes a band. With no band there is nothing to describe,
        # so drop it rather than letting a cleared band keep a stale seed/level.
        if self.opportunity_low is None:
            self.interval_n = None
            self.interval_seed = None
            self.interval_confidence_level = None
            self.interval_computed_at = None
        return self


class ScoreSnapshot(BaseModel):
    """One accepted score state, kept so "did it move?" is a subtraction.

    A snapshot records the score *and* its sample/method companions, because a
    history of bare numbers cannot answer "did the evidence change or the
    estimate?". It is written by one helper on every score-mutating path and
    lives in the append-only event log, so replay reproduces it.

    A snapshot is only written for an *accepted* mutation; a validation failure
    creates neither a score change nor a snapshot.

    The writer appends on every accepted ``update_outcome``, so a metadata-only
    edit (method/count) and an equal-value re-submission each add a snapshot.
    That is deliberate: the trail records that the decision was re-affirmed or
    re-evidenced, and it keeps the count/method-only evidence state visible
    rather than collapsing two unlike states into one identical number.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    outcome_id: str = Field(..., description="The outcome this snapshot belongs to")
    at: str = Field(
        default_factory=utc_now_iso,
        description="ISO-8601 UTC timestamp of the accepted mutation",
    )
    importance: float | None = Field(None, ge=1.0, le=10.0)
    satisfaction: float | None = Field(None, ge=1.0, le=10.0)
    opportunity_score: float | None = None
    importance_n: int | None = Field(None, ge=1)
    satisfaction_n: int | None = Field(None, ge=1)
    method: ScoreMethod = "estimate"
    note: str | None = Field(
        None,
        max_length=SCORE_SNAPSHOT_NOTE_MAX,
        description="Why the number was given, when the caller recorded one",
    )


class SurveyInputSet(BaseModel):
    """The accepted paired survey inputs a band can be reproduced from (B3.1).

    Persisted in the append-only event log so a stored band is reproducible
    after a reload, not only for the process that imported it. Each entry is the
    paired ``(importance, satisfaction)`` a respondent gave, in the canonical
    order the import accepted them, plus a de-identified ``respondent_ref``.

    No personal identifier is stored: ``respondent_ref`` is a caller-supplied
    opaque token (the import's respondent id or a row label), never a name or an
    email, and it is kept only so a repeated respondent stays one person under
    the retention policy. It is not a public aggregate payload.

    ``input_ref`` is the versioned reference the interval slice records: it is
    derived from the inputs so a band can name the exact set it came from, and it
    changes when the set changes. ``study_id``/``wave`` are the lineage links the
    retention decision must define; both are optional here because the policy is
    not yet approved, so a missing link stays ``None`` rather than a guessed
    study.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    outcome_id: str = Field(..., description="The outcome these paired inputs belong to")
    job_id: str = Field(..., description="The owning job, so a cross-job link is detectable")
    input_ref: str = Field(..., description="Versioned reference to this exact input set (B3.1)")
    pairs: list[tuple[float, float]] = Field(
        default_factory=list,
        description="Accepted (importance, satisfaction) pairs in canonical import order",
    )
    respondent_refs: list[str] = Field(
        default_factory=list,
        description="De-identified per-pair respondent tokens, kept only to de-duplicate",
    )
    study_id: str | None = Field(None, description="Study lineage, when the policy defines it")
    wave: str | None = Field(None, description="Study wave lineage, when the policy defines it")
    method: str = Field("survey", description="How the inputs were obtained")

    @model_validator(mode="after")
    def _refs_match_pairs(self) -> SurveyInputSet:
        # A respondent token per pair, or none at all: a partial list would let a
        # caller pair the wrong token with the wrong answers.
        if self.respondent_refs and len(self.respondent_refs) != len(self.pairs):
            raise ValueError("respondent_refs must be empty or one token per pair")
        return self


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
