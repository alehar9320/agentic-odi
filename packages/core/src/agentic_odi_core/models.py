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


ScoreMethod = Literal["estimate", "survey", "import"]

#: What a value estimate counts. The unit is not decoration: ``250000`` currency
#: and ``250000`` hours are different claims, and a reader who cannot see the
#: unit cannot tell which was made.
ValueUnit = Literal["currency", "users", "accounts", "hours"]

#: Where a value estimate came from. ``estimate`` is a judgement; ``market`` and
#: ``pilot`` are the two bases that require a named source (W1/ALH-64), because a
#: number attributed to a market or a pilot has to say which one.
ValueBasis = Literal["estimate", "market", "pilot"]

MAX_VALUE_SOURCE = 200


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
    # Sample size and method (B1/ALH-24). ``None`` is honest: nobody recorded a
    # count. An estimate may not claim a sample, so a count above one requires a
    # non-estimate method — asserted below rather than defaulted to 1.
    importance_n: int | None = Field(None, ge=1, description="People behind the importance score")
    satisfaction_n: int | None = Field(
        None, ge=1, description="People behind the satisfaction score"
    )
    score_method: ScoreMethod = Field(
        "estimate", description="How the scores were obtained: estimate, survey, or import"
    )
    # A recorded judgement with its basis (W1/ALH-64). ``None`` means nobody
    # estimated a value — rendered as ``unsized``, never as a zero. The estimate
    # never derives from the opportunity score and is never summed across
    # outcomes: overlapping estimates would double-count and nobody would notice.
    value_estimate: float | None = Field(
        None, ge=0.0, description="A defensible value estimate, never derived from the score"
    )
    value_unit: ValueUnit | None = Field(
        None, description="What the estimate counts: currency, users, accounts, or hours"
    )
    value_basis: ValueBasis = Field(
        "estimate", description="Where the estimate came from: estimate, market, or pilot"
    )
    value_n: int | None = Field(None, ge=1, description="People behind the value estimate")
    value_source: str | None = Field(
        None, max_length=MAX_VALUE_SOURCE, description="Where a market/pilot estimate came from"
    )

    @model_validator(mode="after")
    def _sample_requires_a_method(self) -> Outcome:
        counts = [n for n in (self.importance_n, self.satisfaction_n) if n is not None]
        if any(n > 1 for n in counts) and self.score_method == "estimate":
            raise ValueError(
                "A sample size above one requires a non-estimate score_method "
                "(survey or import); an estimate cannot have asked anyone."
            )
        return self

    @model_validator(mode="after")
    def _sourced_basis_requires_a_source(self) -> Outcome:
        """A market or pilot estimate must name its source.

        An estimate with no basis is the most common way an ODI readout gets
        discredited in a room; a *sourced* basis with no source is worse, because
        the number looks attributable when it is not.
        """
        if self.value_basis in ("market", "pilot"):
            source = (self.value_source or "").strip()
            if not source:
                raise ValueError(
                    f"A value_basis of {self.value_basis!r} requires a value_source "
                    "naming where the estimate came from."
                )
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


MAX_SNAPSHOT_NOTE = 500


class ScoreSnapshot(BaseModel):
    """An append-only record of an outcome's accepted score state (B6/ALH-29).

    Written by one helper on every score-mutating path, so "did it move?" is a
    subtraction rather than a memory test. The snapshot stores the score *and*
    its sample/method companions: a history of bare numbers cannot answer
    whether the evidence changed or the estimate did.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    outcome_id: str = Field(..., description="The Outcome this snapshot records")
    at: str = Field(..., description="ISO-8601 timestamp, supplied at write time")
    importance: float | None = Field(None, description="Importance score at this moment")
    satisfaction: float | None = Field(None, description="Satisfaction score at this moment")
    opportunity_score: float | None = Field(None, description="Derived opportunity score")
    importance_n: int | None = Field(None, description="Sample size behind importance")
    satisfaction_n: int | None = Field(None, description="Sample size behind satisfaction")
    score_method: ScoreMethod = Field("estimate", description="How the scores were obtained")
    note: str | None = Field(
        None,
        max_length=MAX_SNAPSHOT_NOTE,
        description="Optional reason for the change, at most 500 characters",
    )


class BetStatus(str, Enum):
    """A bet's lifecycle. ``measured`` and ``abandoned`` are terminal."""

    PLANNED = "planned"
    RUNNING = "running"
    MEASURED = "measured"
    ABANDONED = "abandoned"


#: Legal transitions. ``planned`` starts a bet; ``running`` is it underway;
#: ``measured`` is it answered; ``abandoned`` is it dropped. A terminal state
#: has no successors, so an illegal transition can name the legal ones.
BET_TRANSITIONS: dict[BetStatus, tuple[BetStatus, ...]] = {
    BetStatus.PLANNED: (BetStatus.RUNNING, BetStatus.ABANDONED),
    BetStatus.RUNNING: (BetStatus.MEASURED,),
    BetStatus.MEASURED: (),
    BetStatus.ABANDONED: (),
}

#: Terminal states, derived so they cannot drift from ``BET_TRANSITIONS``.
TERMINAL_BET_STATUSES: frozenset[BetStatus] = frozenset(
    status for status, successors in BET_TRANSITIONS.items() if not successors
)


class Bet(BaseModel):
    """A recorded expectation: a hypothesis with a baseline that cannot drift.

    ``baseline`` is captured at creation and stored, never recomputed, because
    the whole point of a bet is that its starting point does not move with the
    score. ``measure_by`` is a date, not a datetime: a bet is looked at on a day.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = Field(..., description="The Decision this bet follows from")
    outcome_id: str = Field(..., description="The Outcome this bet targets")
    hypothesis: str = Field(..., min_length=1, description="What we expect to happen")
    baseline: float = Field(..., description="The score captured at creation, never recomputed")
    target: float = Field(..., description="The score we expect to reach")
    measure_by: str = Field(..., description="ISO-8601 date we will look at the number")
    status: BetStatus = Field(BetStatus.PLANNED)
    measured_at: str | None = Field(None, description="ISO-8601 timestamp when measured")

    def next_statuses(self) -> tuple[BetStatus, ...]:
        """The legal successors of the current status, or ``()`` when terminal."""
        return BET_TRANSITIONS[self.status]

    def is_terminal(self) -> bool:
        return self.status in TERMINAL_BET_STATUSES


class SegmentOrigin(str, Enum):
    """Where a segment came from: a person typed it, or a person accepted a candidate."""

    MANUAL = "manual"
    CANDIDATE = "candidate"


class Segment(BaseModel):
    """A named group defined by the outcomes it cares about (D1/ALH-40).

    Never by demographics: outcome-based segmentation is the method's actual
    claim, and a demographics column would make the feature wrong rather than
    merely incomplete. ``outcome_ids`` is the stored membership, so a segment
    means the same thing next quarter; ``criterion`` is free text saying *why*
    the group is coherent. The members are the definition — not a filter
    re-evaluated on read.

    ``origin`` records whether a person typed the segment or accepted a derived
    candidate (D2.2/ALH-161); a hand-made and an accepted segment differ only
    here, so both stay ordinary segments.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The Job this segment's members belong to")
    name: str = Field(..., min_length=1, description="The segment's name")
    criterion: str = Field(
        ..., min_length=1, description="Why this group is coherent — free text, never a filter"
    )
    outcome_ids: list[str] = Field(
        ..., min_length=1, description="The member Outcome IDs that define the segment"
    )
    notes: str | None = Field(None, description="Optional free-text notes")
    origin: SegmentOrigin = Field(
        SegmentOrigin.MANUAL, description="manual, or candidate when accepted from a proposal"
    )
    candidate_fingerprint: str | None = Field(
        None, description="The accepted candidate's stable fingerprint, when origin is candidate"
    )


class StrategyKind(str, Enum):
    """The three ODI strategy paths (D4/ALH-43). There is no fourth."""

    DIFFERENTIATED = "differentiated"
    DISRUPTIVE = "disruptive"
    NEW_MARKET = "new_market"


class Strategy(BaseModel):
    """A recorded strategy for a segment, with the reasoning and expected effect.

    The kind is stored with the rationale so the choice is not a slogan: the
    guardrail in ``services.choose_strategy`` refuses a kind whose data
    precondition the segment's profile does not meet.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    segment_id: str = Field(..., description="The Segment this strategy is for")
    kind: StrategyKind = Field(..., description="differentiated, disruptive, or new_market")
    rationale: str = Field(
        ..., min_length=1, description="Why this strategy, in the caller's words"
    )
    chosen_at: str = Field(..., description="ISO-8601 timestamp, supplied at write time")
    expected_effect: str = Field(
        ..., min_length=1, description="What the caller expects this to change"
    )


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
