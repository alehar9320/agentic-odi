"""Core domain models for Agentic ODI."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, computed_field, model_validator

from agentic_odi_core.errors import ValidationError as DomainValidationError


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


#: The V2MOM lists an outcome may advance. The vision is a statement, values
#: are principles, and obstacles are risks, so none of them is a target.
ObjectiveField = Literal["method", "measure"]


class OutcomeAlignment(BaseModel):
    """A claim that an Outcome advances one V2MOM objective.

    ``field`` is ``method`` or ``measure``; ``key`` is the content key computed
    from ``field`` and ``text`` when the link was made; ``text`` is the
    canonical objective text then. Storing the key *and* the text means a
    reworded objective shows up as drift carrying the text the outcome was
    linked to, and the key is never re-derived under a later normalization rule.
    """

    field: ObjectiveField = Field(..., description="Which V2MOM list the objective lives in")
    key: str = Field(..., description="Frozen content key for the objective text")
    text: str = Field(..., description="The objective text as it read when the link was made")


class ClaimSkip(BaseModel):
    """One question that went unanswered, and why it was skipped.

    A skip without a reason is not a skip, it is a missing answer, so
    ``reason`` is required and must not be blank.
    """

    question: str = Field(..., description="The question that was not answered")
    reason: str = Field(..., description="Why it was skipped; never blank")


class ClaimCheck(BaseModel):
    """The questions behind a score: what was asked, answered, or skipped.

    Two numbers are not provenance. A score that carries a claim check says
    which questions produced it — ``asked`` — and what came back: the
    ``answers`` the person gave and the ``skips`` with a recorded reason.

    ``verified`` is derived, never typed in: a check is verified when at least
    one question was answered by the person. A check of only skips is
    unverified, so an outcome built on an assumption says so instead of
    borrowing the confidence of a number.
    """

    asked: list[str] = Field(default_factory=list, description="The questions put to the person")
    answers: list[str] = Field(
        default_factory=list, description="The answers the person gave, in order"
    )
    skips: list[ClaimSkip] = Field(
        default_factory=list, description="Questions skipped, each with a reason"
    )

    @computed_field
    @property
    def verified(self) -> bool:
        return bool(self.answers)


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
    trace: list[OutcomeAlignment] = Field(
        default_factory=list,
        description=(
            "The V2MOM methods and measures this outcome advances. Empty means "
            "the outcome is unlinked, which the traceability report calls an orphan."
        ),
    )
    claim_check: ClaimCheck | None = Field(
        None, description="The questions that produced the score, and what came back"
    )
    study_id: str | None = Field(
        None,
        description="The Study wave this outcome was measured in, or None for a row that predates studies",
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
    impact: Literal["high", "medium", "low"] = Field(
        "medium",
        description=(
            "How much this evidence moves the outcome score; mirrors JPD's insights impact rating"
        ),
    )
    confidence: Literal["verified", "claimed"] = Field(
        "claimed",
        description=(
            "Whether the record was confirmed by the person (verified) or "
            "asserted without confirmation (claimed)"
        ),
    )


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


class StudyStatus(str, Enum):
    """Where a study is in its own life: opened, collecting, or closed."""

    PLANNED = "planned"
    FIELDING = "fielding"
    CLOSED = "closed"


class Study(BaseModel):
    """One named pass over a Job, and the wave number of that pass.

    A study is a container, not a measurement: it names a slice of research so a
    later wave can be compared with an earlier one. ``wave`` is unique per
    ``(job_id, name)`` within the store — that guarantee needs to see the other
    rows, so it lives in the service, while the model owns the invariants it can
    check alone: a wave is a positive pass number, and ``closed_at`` appears if
    and only if the study is closed.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = Field(..., description="The Job this study takes one pass over")
    name: str = Field(..., description="Human label for the study, e.g. 'reconciliation sweep'")
    wave: int = Field(..., ge=1, description="1-based pass number within (job_id, name)")
    status: StudyStatus = Field(StudyStatus.PLANNED, description="Where the study is in its life")
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: datetime | None = Field(None, description="Set once, when the study closes")
    method_notes: str | None = Field(
        None, description="How this pass was run, so a later wave is comparable"
    )

    @model_validator(mode="after")
    def _closure_matches_status(self) -> Study:
        if self.status is StudyStatus.CLOSED and self.closed_at is None:
            raise ValueError("A closed study must carry a closed_at")
        if self.status is not StudyStatus.CLOSED and self.closed_at is not None:
            raise ValueError("Only a closed study may carry a closed_at")
        return self


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
    computed_at_event_id: int | None = Field(
        None,
        description=(
            "The store revision this segment was derived from. None when it was "
            "derived before the field existed, which reads as unknown, not fresh."
        ),
    )
    stale: bool | None = Field(
        None,
        description=(
            "Computed at read time, never stored: whether the store has moved on "
            "since computed_at_event_id. None when no read has labelled it yet."
        ),
    )
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
    computed_at_event_id: int | None = Field(
        None,
        description=(
            "The store revision this strategy was derived from. None when it was "
            "derived before the field existed, which reads as unknown, not fresh."
        ),
    )
    stale: bool | None = Field(
        None,
        description=(
            "Computed at read time, never stored: whether the store has moved on "
            "since computed_at_event_id. None when no read has labelled it yet."
        ),
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
        ...,
        description="sha256 of kind|subject_kind|subject_id|discriminator, plus source event id",
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


class EntityType(str, Enum):
    """The kinds of ODI entity a link can point at.

    Closed on purpose: an open string lets one writer say ``serves`` and
    another ``implements`` for the same meaning, and the graph stops being
    queryable. There is no ``candidate`` member — no such model exists.
    """

    JOB = "job"
    STEP = "step"
    OUTCOME = "outcome"
    EVIDENCE = "evidence"
    SEGMENT = "segment"
    STRATEGY = "strategy"


class RelationshipType(str, Enum):
    """The closed vocabulary of typed edges between two ODI entities.

    Five values, no more. An external target (a Jira ticket, a Linear issue)
    is ``relates_to`` plus ``external_system`` and ``external_id``, not a
    relationship value of its own.
    """

    EVIDENCE_FOR = "evidence_for"
    OUTCOME_OF = "outcome_of"
    BLOCKED_BY = "blocked_by"
    DUPLICATES = "duplicates"
    RELATES_TO = "relates_to"


class ExternalSystem(str, Enum):
    """A system outside Agentic ODI that a link can point at."""

    JIRA = "jira"
    LINEAR = "linear"
    JPD = "jpd"
    GITHUB = "github"
    NOTION = "notion"


_ANY_ENTITY: frozenset[EntityType] = frozenset(EntityType)

# The single source of truth for which (source, target) entity pairs each
# relationship permits. ``LINK_SAME_TYPE_RELATIONSHIPS`` refines the entries
# whose target must be the source's own type rather than any entity.
LINK_PAIR_RULES: dict[RelationshipType, tuple[frozenset[EntityType], frozenset[EntityType]]] = {
    RelationshipType.EVIDENCE_FOR: (
        frozenset({EntityType.EVIDENCE}),
        frozenset({EntityType.OUTCOME, EntityType.STEP, EntityType.JOB}),
    ),
    RelationshipType.OUTCOME_OF: (
        frozenset({EntityType.OUTCOME}),
        frozenset({EntityType.STEP, EntityType.JOB}),
    ),
    RelationshipType.BLOCKED_BY: (_ANY_ENTITY, _ANY_ENTITY),
    RelationshipType.DUPLICATES: (_ANY_ENTITY, _ANY_ENTITY),
    RelationshipType.RELATES_TO: (_ANY_ENTITY, _ANY_ENTITY),
}

LINK_SAME_TYPE_RELATIONSHIPS: frozenset[RelationshipType] = frozenset({RelationshipType.DUPLICATES})


def _unwrap_domain_validation_error(exc: ValidationError) -> DomainValidationError | None:
    """Recover the domain error Pydantic wrapped, or ``None`` if it did not.

    Pydantic folds any ``ValueError`` raised in a validator into its own
    ``ValidationError``. The domain error is a ``ValueError`` subclass, so its
    identity is carried in ``ctx['error']`` and has to be pulled back out.
    """
    for error in exc.errors():
        inner = error.get("ctx", {}).get("error")
        if isinstance(inner, DomainValidationError):
            return inner
    return None


#: The full set of relationship kinds, as plain strings, for consumers that do
#: not want to import the enum (e.g. JSON-deserializing a row back into a link).
LINK_RELATIONSHIP_TYPES: list[str] = [member.value for member in RelationshipType]


class Link(BaseModel):
    """A first-class typed edge between two ODI entities.

    A link says "this evidence supports that outcome" or "this outcome is a
    step of that job" as structured data a query can answer, instead of prose
    a reader has to interpret. A human approves each link before it is
    written; this model owns only the invariants it can check alone.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_type: EntityType = Field(..., description="The type of the source entity")
    source_id: str = Field(..., description="The ID of the source entity")
    target_type: EntityType = Field(..., description="The type of the target entity")
    target_id: str = Field(..., description="The ID of the target entity")
    relationship_type: RelationshipType = Field(..., description="The type of relationship")
    external_system: ExternalSystem | None = Field(
        None, description="External system the target lives in, if any"
    )
    external_id: str | None = Field(None, description="Target ID inside that external system")
    preview: dict[str, Any] | None = Field(None, description="Cached preview of the target entity")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the link was created",
    )

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except ValidationError as exc:
            domain_error = _unwrap_domain_validation_error(exc)
            if domain_error is None:
                raise
            raise domain_error from None

    @model_validator(mode="after")
    def _link_is_closed_and_honest(self) -> Link:
        if self.source_type is self.target_type and self.source_id == self.target_id:
            raise DomainValidationError(
                f"A link cannot point at itself: {self.source_type.value} {self.source_id}"
            )

        allowed_sources, allowed_targets = LINK_PAIR_RULES[self.relationship_type]
        if self.source_type not in allowed_sources or self.target_type not in allowed_targets:
            targets = ", ".join(sorted(t.value for t in allowed_targets))
            raise DomainValidationError(
                f"{self.relationship_type.value} cannot link "
                f"{self.source_type.value} to {self.target_type.value}; "
                f"allowed targets are: {targets}"
            )

        if self.relationship_type in LINK_SAME_TYPE_RELATIONSHIPS and (
            self.target_type is not self.source_type
        ):
            raise DomainValidationError(
                f"{self.relationship_type.value} requires both ends to be the same "
                f"entity type; got {self.source_type.value} and {self.target_type.value}"
            )

        if (self.external_system is None) != (self.external_id is None):
            raise DomainValidationError(
                "external_system and external_id must be set together or both omitted"
            )
        return self
