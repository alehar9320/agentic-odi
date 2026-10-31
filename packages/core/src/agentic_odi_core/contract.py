"""Single source of truth for the MCP tool surface.

Adapters must use :class:`ToolName` instead of hard-coded strings, and the
contract test in ``tests/contract`` asserts that the live FastMCP registry
matches :data:`TOOL_SPECS`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum


class ToolName(str, Enum):
    ADD_JOB = "add_job"
    GET_JOBS = "get_jobs"
    GET_JOB = "get_job"
    UPDATE_JOB = "update_job"
    DELETE_JOB = "delete_job"
    ADD_STEP = "add_step"
    GET_JOB_MAP = "get_job_map"
    GET_STEP = "get_step"
    UPDATE_STEP = "update_step"
    DELETE_STEP = "delete_step"
    ADD_OUTCOME = "add_outcome"
    GET_OUTCOMES = "get_outcomes"
    GET_OUTCOME = "get_outcome"
    UPDATE_OUTCOME = "update_outcome"
    DELETE_OUTCOME = "delete_outcome"
    ADD_CUSTOMER_OUTCOME = "add_customer_outcome"
    GET_CUSTOMER_OUTCOME = "get_customer_outcome"
    LIST_CUSTOMER_OUTCOMES = "list_customer_outcomes"
    UPDATE_CUSTOMER_OUTCOME = "update_customer_outcome"
    DELETE_CUSTOMER_OUTCOME = "delete_customer_outcome"
    ADD_EVIDENCE = "add_evidence"
    GET_EVIDENCE = "get_evidence"
    LIST_EVIDENCE = "list_evidence"
    DELETE_EVIDENCE = "delete_evidence"
    PROMOTE_EVIDENCE = "promote_evidence"
    COMPARE_OUTCOMES = "compare_outcomes"
    SET_OUTCOME_VALUE = "set_outcome_value"
    GET_ROADMAP = "get_roadmap"
    RECORD_DECISION = "record_decision"
    GET_DECISION = "get_decision"
    LIST_DECISIONS = "list_decisions"
    REVIEW_DECISION = "review_decision"
    RENDER_MEMO = "render_memo"
    GET_OUTCOME_HISTORY = "get_outcome_history"
    GET_OUTCOME_DELTA = "get_outcome_delta"
    RECORD_BET = "record_bet"
    GET_BET = "get_bet"
    LIST_BETS = "list_bets"
    ADVANCE_BET = "advance_bet"
    ADD_SEGMENT = "add_segment"
    GET_SEGMENT = "get_segment"
    LIST_SEGMENTS = "list_segments"
    DELETE_SEGMENT = "delete_segment"
    SUGGEST_SEGMENTS = "suggest_segments"
    ACCEPT_SEGMENT_CANDIDATE = "accept_segment_candidate"
    GET_SEGMENT_PROFILE = "get_segment_profile"
    CHOOSE_STRATEGY = "choose_strategy"
    GET_STRATEGY = "get_strategy"
    LIST_STRATEGIES = "list_strategies"
    EVALUATE_OUTCOME = "evaluate_outcome"
    GET_ODI_SCHEMA = "get_odi_schema"
    COMPUTE_OPPORTUNITY = "compute_opportunity"
    GET_FRAMEWORK_GUIDELINES = "get_odi_framework_guidelines"
    GET_CAPABILITIES = "get_capabilities"
    GET_CAPABILITIES_MANIFEST = "get_capabilities_manifest"
    LIST_SIGNALS = "list_signals"
    MARK_SIGNAL_READ = "mark_signal_read"
    DISMISS_SIGNAL = "dismiss_signal"
    GET_HEALTH = "get_health"
    SCHEDULE_WORK = "schedule_work"
    GET_SCHEDULED_WORK = "get_scheduled_work"
    LIST_SCHEDULED_WORK = "list_scheduled_work"
    CANCEL_SCHEDULED_WORK = "cancel_scheduled_work"
    TRIGGER_SCHEDULED_WORK = "trigger_scheduled_work"


class ToolEffect(str, Enum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class ToolSpec:
    """Metadata for a single MCP tool: its name, human-readable summary,
    effect (read/write/destructive), arguments, required subset, return
    description, and ODI stage."""

    name: str
    summary: str
    effect: ToolEffect
    arguments: tuple[str, ...] = field(default_factory=tuple)
    required: tuple[str, ...] = field(default_factory=tuple)
    returns: str = ""
    stage: str | None = None


def _derive_effect(name: str) -> ToolEffect:
    """Derive a tool's effect from its name.

    get_*/list_*/render_* → READ, delete_* → DESTRUCTIVE, everything else → WRITE.
    A renderer projects what is already recorded and writes nothing, so it is
    read-only by the same rule that governs a getter.
    """
    if name.startswith(("get_", "list_", "render_")):
        return ToolEffect.READ
    if name.startswith("delete_"):
        return ToolEffect.DESTRUCTIVE
    return ToolEffect.WRITE


TOOL_SPECS: dict[str, ToolSpec] = {
    ToolName.ADD_JOB.value: ToolSpec(
        name="add_job",
        summary="Create a new Job-to-be-Done.",
        effect=_derive_effect("add_job"),
        arguments=("name", "description"),
        required=("name",),
        returns="The created Job.",
        stage="1",
    ),
    ToolName.GET_JOBS.value: ToolSpec(
        name="get_jobs",
        summary="List all Jobs.",
        effect=_derive_effect("get_jobs"),
        arguments=("limit", "offset"),
        returns="A list of Jobs.",
        stage="1",
    ),
    ToolName.GET_JOB.value: ToolSpec(
        name="get_job",
        summary="Get a single Job by ID.",
        effect=_derive_effect("get_job"),
        arguments=("job_id",),
        required=("job_id",),
        returns="The Job, or an error string if not found.",
        stage="1",
    ),
    ToolName.UPDATE_JOB.value: ToolSpec(
        name="update_job",
        summary="Update a Job's name or description.",
        effect=_derive_effect("update_job"),
        arguments=("job_id", "name", "description"),
        required=("job_id",),
        returns="The updated Job.",
        stage="1",
    ),
    ToolName.DELETE_JOB.value: ToolSpec(
        name="delete_job",
        summary="Delete a Job and its cascading dependents.",
        effect=_derive_effect("delete_job"),
        arguments=("job_id",),
        required=("job_id",),
        returns="The deleted Job ID.",
        stage="1",
    ),
    ToolName.ADD_STEP.value: ToolSpec(
        name="add_step",
        summary="Add a step to a Job's job map.",
        effect=_derive_effect("add_step"),
        arguments=("job_id", "name", "order", "stage", "allow_empty_job_map"),
        required=("job_id", "name", "order"),
        returns="The created Step.",
        stage="3",
    ),
    ToolName.GET_JOB_MAP.value: ToolSpec(
        name="get_job_map",
        summary="Get the ordered job map for a Job.",
        effect=_derive_effect("get_job_map"),
        arguments=("job_id", "limit", "offset"),
        required=("job_id",),
        returns="A list of Steps ordered by stage.",
        stage="3",
    ),
    ToolName.GET_STEP.value: ToolSpec(
        name="get_step",
        summary="Get a single Step by ID.",
        effect=_derive_effect("get_step"),
        arguments=("step_id",),
        required=("step_id",),
        returns="The Step, or an error string if not found.",
        stage="3",
    ),
    ToolName.UPDATE_STEP.value: ToolSpec(
        name="update_step",
        summary="Update a Step's name or order.",
        effect=_derive_effect("update_step"),
        arguments=("step_id", "name", "order"),
        required=("step_id",),
        returns="The updated Step.",
        stage="3",
    ),
    ToolName.DELETE_STEP.value: ToolSpec(
        name="delete_step",
        summary="Delete a Step and its cascading dependents.",
        effect=_derive_effect("delete_step"),
        arguments=("step_id",),
        required=("step_id",),
        returns="The deleted Step ID.",
        stage="3",
    ),
    ToolName.ADD_OUTCOME.value: ToolSpec(
        name="add_outcome",
        summary="Add a desired Outcome to a Job.",
        effect=_derive_effect("add_outcome"),
        arguments=(
            "job_id",
            "statement",
            "importance",
            "satisfaction",
            "step_id",
            "importance_n",
            "satisfaction_n",
            "score_method",
        ),
        required=("job_id", "statement", "importance", "satisfaction"),
        returns="The created Outcome.",
        stage="2",
    ),
    ToolName.GET_OUTCOMES.value: ToolSpec(
        name="get_outcomes",
        summary="List desired Outcomes for a Job.",
        effect=_derive_effect("get_outcomes"),
        arguments=("job_id", "step_id", "limit", "offset", "sort"),
        required=("job_id",),
        returns="A list of Outcomes.",
        stage="2",
    ),
    ToolName.GET_OUTCOME.value: ToolSpec(
        name="get_outcome",
        summary="Get a single Outcome by ID.",
        effect=_derive_effect("get_outcome"),
        arguments=("outcome_id",),
        required=("outcome_id",),
        returns="The Outcome, or an error string if not found.",
        stage="2",
    ),
    ToolName.UPDATE_OUTCOME.value: ToolSpec(
        name="update_outcome",
        summary="Update an Outcome's statement or scores.",
        effect=_derive_effect("update_outcome"),
        arguments=(
            "outcome_id",
            "statement",
            "importance",
            "satisfaction",
            "step_id",
            "importance_n",
            "satisfaction_n",
            "score_method",
            "at",
            "note",
        ),
        required=("outcome_id",),
        returns="The updated Outcome.",
        stage="2",
    ),
    ToolName.DELETE_OUTCOME.value: ToolSpec(
        name="delete_outcome",
        summary="Delete a desired Outcome.",
        effect=_derive_effect("delete_outcome"),
        arguments=("outcome_id",),
        required=("outcome_id",),
        returns="The deleted Outcome ID.",
        stage="2",
    ),
    ToolName.ADD_CUSTOMER_OUTCOME.value: ToolSpec(
        name="add_customer_outcome",
        summary="Add a Customer Outcome pairing customer and business value.",
        effect=_derive_effect("add_customer_outcome"),
        arguments=(
            "job_id",
            "customer_value",
            "business_value",
            "step_id",
        ),
        required=("job_id", "customer_value", "business_value"),
        returns="The created Customer Outcome.",
    ),
    ToolName.GET_CUSTOMER_OUTCOME.value: ToolSpec(
        name="get_customer_outcome",
        summary="Get a single Customer Outcome by ID.",
        effect=_derive_effect("get_customer_outcome"),
        arguments=("outcome_id",),
        required=("outcome_id",),
        returns="The Customer Outcome, or an error string if not found.",
    ),
    ToolName.LIST_CUSTOMER_OUTCOMES.value: ToolSpec(
        name="list_customer_outcomes",
        summary="List Customer Outcomes for a Job.",
        effect=_derive_effect("list_customer_outcomes"),
        arguments=("job_id", "limit", "offset"),
        returns="A list of Customer Outcomes.",
    ),
    ToolName.UPDATE_CUSTOMER_OUTCOME.value: ToolSpec(
        name="update_customer_outcome",
        summary="Update a Customer Outcome's value metrics.",
        effect=_derive_effect("update_customer_outcome"),
        arguments=(
            "outcome_id",
            "direction",
            "unit_of_measure",
            "object_of_control",
            "contextual_clarifier",
            "statement",
            "importance",
            "satisfaction",
            "category",
            "business_statement",
            "detail",
            "estimated_annual_value",
            "confidence",
            "step_id",
            "value_metrics",
        ),
        required=("outcome_id",),
        returns="The updated Customer Outcome.",
    ),
    ToolName.DELETE_CUSTOMER_OUTCOME.value: ToolSpec(
        name="delete_customer_outcome",
        summary="Delete a Customer Outcome.",
        effect=_derive_effect("delete_customer_outcome"),
        arguments=("outcome_id",),
        required=("outcome_id",),
        returns="The deleted Customer Outcome ID.",
    ),
    ToolName.ADD_EVIDENCE.value: ToolSpec(
        name="add_evidence",
        summary="Capture an evidence record from a connector.",
        effect=_derive_effect("add_evidence"),
        arguments=(
            "source_name",
            "source_kind",
            "name",
            "content",
            "url",
            "item_type",
            "raw",
            "job_id",
            "step_id",
            "outcome_id",
        ),
        required=("source_name", "source_kind", "name", "content"),
        returns="The created Evidence record.",
    ),
    ToolName.GET_EVIDENCE.value: ToolSpec(
        name="get_evidence",
        summary="Get a single evidence record by ID.",
        effect=_derive_effect("get_evidence"),
        arguments=("evidence_id",),
        required=("evidence_id",),
        returns="The Evidence record, or an error string if not found.",
    ),
    ToolName.LIST_EVIDENCE.value: ToolSpec(
        name="list_evidence",
        summary="List evidence records, optionally filtered by job/step/outcome.",
        effect=_derive_effect("list_evidence"),
        arguments=("job_id", "step_id", "outcome_id", "limit", "offset"),
        returns="A list of Evidence records.",
    ),
    ToolName.DELETE_EVIDENCE.value: ToolSpec(
        name="delete_evidence",
        summary="Delete an evidence record.",
        effect=_derive_effect("delete_evidence"),
        arguments=("evidence_id",),
        required=("evidence_id",),
        returns="The deleted Evidence ID.",
    ),
    ToolName.PROMOTE_EVIDENCE.value: ToolSpec(
        name="promote_evidence",
        summary="Promote evidence to a Job or an Outcome.",
        effect=_derive_effect("promote_evidence"),
        arguments=(
            "evidence_id",
            "target",
            "job_id",
            "statement",
            "name",
            "importance",
            "satisfaction",
        ),
        required=("evidence_id", "target"),
        returns="The created Job or Outcome.",
    ),
    ToolName.EVALUATE_OUTCOME.value: ToolSpec(
        name="evaluate_outcome",
        summary="Evaluate an outcome statement against ODI format rules.",
        effect=_derive_effect("evaluate_outcome"),
        arguments=("statement", "job_id"),
        required=("statement",),
        returns="A verdict with coded issues and suggestions.",
        stage="2",
    ),
    ToolName.COMPARE_OUTCOMES.value: ToolSpec(
        name="compare_outcomes",
        summary=(
            "Align two or three outcomes on the same axes: one row per metric, "
            "one column per outcome. Never names a winner."
        ),
        effect=_derive_effect("compare_outcomes"),
        arguments=("outcome_ids",),
        required=("outcome_ids",),
        returns=(
            "Aligned rows over the given column order. A metric nobody measured "
            "renders 'not measured'; a real 0 stays 0."
        ),
        stage="6",
    ),
    ToolName.SET_OUTCOME_VALUE.value: ToolSpec(
        name="set_outcome_value",
        summary=(
            "Record what an outcome is worth, with its unit and its basis. A "
            "market or pilot estimate requires a source; a cleared estimate "
            "clears its companions."
        ),
        effect=_derive_effect("set_outcome_value"),
        arguments=("outcome_id", "estimate", "unit", "basis", "n", "source"),
        required=("outcome_id", "estimate"),
        returns=(
            "The updated Outcome. An outcome with no estimate is 'unsized'; "
            "value is never derived from the opportunity score."
        ),
        stage="6",
    ),
    ToolName.GET_ROADMAP.value: ToolSpec(
        name="get_roadmap",
        summary=(
            "Derive a job's outcome roadmap from its recorded decisions: one "
            "entry per chosen outcome, grouped by the quarter its decision was "
            "made. Undecided outcomes are excluded and counted."
        ),
        effect=_derive_effect("get_roadmap"),
        arguments=("job_id", "horizon", "today"),
        required=("job_id",),
        returns=(
            "The roadmap entries in date order plus the excluded count and its "
            "reason. A baseline nobody measured renders 'not measured'."
        ),
        stage="6",
    ),
    ToolName.RECORD_DECISION.value: ToolSpec(
        name="record_decision",
        summary="Record a decision: what was chosen, what was rejected, and why.",
        effect=_derive_effect("record_decision"),
        arguments=(
            "job_id",
            "chosen_outcome_ids",
            "rationale",
            "decided_by",
            "decided_at",
            "rejected",
            "confidence",
            "supersedes",
        ),
        required=(
            "job_id",
            "chosen_outcome_ids",
            "rationale",
            "decided_by",
            "decided_at",
        ),
        returns="The recorded Decision, with a superseded predecessor kept readable.",
        stage="6",
    ),
    ToolName.GET_DECISION.value: ToolSpec(
        name="get_decision",
        summary="Get a single recorded decision by ID.",
        effect=_derive_effect("get_decision"),
        arguments=("decision_id",),
        required=("decision_id",),
        returns="The Decision, or an error string if not found.",
        stage="6",
    ),
    ToolName.LIST_DECISIONS.value: ToolSpec(
        name="list_decisions",
        summary="List a job's decision history, oldest first.",
        effect=_derive_effect("list_decisions"),
        arguments=("job_id", "limit", "offset"),
        required=("job_id",),
        returns="An ordered list of Decisions, including superseded ones.",
        stage="6",
    ),
    ToolName.REVIEW_DECISION.value: ToolSpec(
        name="review_decision",
        summary=(
            "Re-examine a past decision against today's numbers. Each chosen "
            "outcome is improved, degraded, no change, no evidence, or orphaned."
        ),
        effect=_derive_effect("review_decision"),
        arguments=("decision_id", "today"),
        required=("decision_id", "today"),
        returns=(
            "The review: days elapsed and, per chosen outcome, its state. A "
            "missing measurement is 'no evidence', never 'no change'."
        ),
        stage="6",
    ),
    ToolName.RENDER_MEMO.value: ToolSpec(
        name="render_memo",
        summary=(
            "Assemble the decision memo from what is already recorded: the "
            "decision, why now, the evidence with citations, the rejected "
            "options, the value, the success criteria and bet, and the holes."
        ),
        effect=ToolEffect.READ,
        arguments=("decision_id",),
        required=("decision_id",),
        returns=(
            "The rendered memo markdown. A missing section is omitted with a "
            "one-line reason; no number is invented and none is rendered as zero."
        ),
        stage="6",
    ),
    ToolName.GET_OUTCOME_HISTORY.value: ToolSpec(
        name="get_outcome_history",
        summary="Every recorded score snapshot for an outcome, oldest first.",
        effect=_derive_effect("get_outcome_history"),
        arguments=("outcome_id",),
        required=("outcome_id",),
        returns="The snapshots in chronological order; empty when nothing is recorded.",
        stage="6",
    ),
    ToolName.GET_OUTCOME_DELTA.value: ToolSpec(
        name="get_outcome_delta",
        summary=(
            "The signed change for an outcome between the nearest snapshot at or "
            "before 'since' (or the earliest) and the latest."
        ),
        effect=_derive_effect("get_outcome_delta"),
        arguments=("outcome_id", "since"),
        required=("outcome_id",),
        returns=(
            "Signed importance, satisfaction and opportunity deltas plus a "
            "direction. A metric nobody measured is null, never 0."
        ),
        stage="6",
    ),
    ToolName.RECORD_BET.value: ToolSpec(
        name="record_bet",
        summary=(
            "Record a bet: a hypothesis with a baseline captured at creation, a "
            "target, and a date to look at the number."
        ),
        effect=_derive_effect("record_bet"),
        arguments=(
            "decision_id",
            "outcome_id",
            "hypothesis",
            "target",
            "measure_by",
            "baseline",
        ),
        required=("decision_id", "outcome_id", "hypothesis", "target", "measure_by"),
        returns="The created Bet, with its baseline stored rather than recomputed.",
        stage="6",
    ),
    ToolName.GET_BET.value: ToolSpec(
        name="get_bet",
        summary="Get a single bet by ID.",
        effect=_derive_effect("get_bet"),
        arguments=("bet_id",),
        required=("bet_id",),
        returns="The Bet, or an error string if not found.",
        stage="6",
    ),
    ToolName.LIST_BETS.value: ToolSpec(
        name="list_bets",
        summary="List bets, filtered by job or decision.",
        effect=_derive_effect("list_bets"),
        arguments=("job_id", "decision_id", "limit", "offset"),
        required=(),
        returns="The bets in creation order.",
        stage="6",
    ),
    ToolName.ADVANCE_BET.value: ToolSpec(
        name="advance_bet",
        summary=(
            "Move a bet to a new status. planned -> running -> measured, or "
            "planned -> abandoned. An illegal transition is refused and names "
            "the legal ones."
        ),
        effect=_derive_effect("advance_bet"),
        arguments=("bet_id", "status", "at"),
        required=("bet_id", "status"),
        returns="The updated Bet.",
        stage="6",
    ),
    ToolName.ADD_SEGMENT.value: ToolSpec(
        name="add_segment",
        summary=(
            "Create a segment: a named group of a job's outcomes defined by the "
            "outcomes it cares about. No demographic fields exist, by design."
        ),
        effect=_derive_effect("add_segment"),
        arguments=("job_id", "name", "criterion", "outcome_ids", "notes", "origin"),
        required=("job_id", "name", "criterion", "outcome_ids"),
        returns=(
            "The created Segment. A member that is missing or belongs to another "
            "job is refused before any write."
        ),
        stage="6",
    ),
    ToolName.GET_SEGMENT.value: ToolSpec(
        name="get_segment",
        summary="Get a single segment by ID.",
        effect=_derive_effect("get_segment"),
        arguments=("segment_id",),
        required=("segment_id",),
        returns="The Segment, or an error string if not found.",
        stage="6",
    ),
    ToolName.LIST_SEGMENTS.value: ToolSpec(
        name="list_segments",
        summary="List segments, optionally filtered by job.",
        effect=_derive_effect("list_segments"),
        arguments=("job_id", "limit", "offset"),
        required=(),
        returns="The segments in creation order.",
        stage="6",
    ),
    ToolName.DELETE_SEGMENT.value: ToolSpec(
        name="delete_segment",
        summary=(
            "Delete a segment. Outcomes are never touched — only the lens on them is removed."
        ),
        effect=_derive_effect("delete_segment"),
        arguments=("segment_id",),
        required=("segment_id",),
        returns="Nothing on success; an error string if not found.",
        stage="6",
    ),
    ToolName.SUGGEST_SEGMENTS.value: ToolSpec(
        name="suggest_segments",
        summary=(
            "Propose segment candidates from the scores: deterministic groups over "
            "band and importance decile. Persists nothing."
        ),
        effect=_derive_effect("suggest_segments"),
        arguments=("job_id",),
        required=("job_id",),
        returns=(
            "The candidates with their member outcomes and a stable fingerprint, "
            "or a reason no group clears the bar. Writes nothing."
        ),
        stage="6",
    ),
    ToolName.ACCEPT_SEGMENT_CANDIDATE.value: ToolSpec(
        name="accept_segment_candidate",
        summary=(
            "Accept a suggested candidate into a segment, matched by its stable "
            "fingerprint. A stale fingerprint is refused; a repeat accept is "
            "idempotent."
        ),
        effect=_derive_effect("accept_segment_candidate"),
        arguments=("job_id", "fingerprint", "name", "criterion"),
        required=("job_id", "fingerprint"),
        returns="The created (or already-created) Segment.",
        stage="6",
    ),
    ToolName.GET_SEGMENT_PROFILE.value: ToolSpec(
        name="get_segment_profile",
        summary=(
            "Read a segment's servability: counts and the top underserved and "
            "overserved outcomes, kept separate. A ratio of nothing is null, "
            "never 0."
        ),
        effect=_derive_effect("get_segment_profile"),
        arguments=("segment_id",),
        required=("segment_id",),
        returns="The segment profile, including any missing members as gaps.",
        stage="6",
    ),
    ToolName.CHOOSE_STRATEGY.value: ToolSpec(
        name="choose_strategy",
        summary=(
            "Record a strategy for a segment. Each kind has a guardrail that names "
            "the missing condition; new-market is refused while alternatives "
            "evidence is absent."
        ),
        effect=_derive_effect("choose_strategy"),
        arguments=("segment_id", "kind", "rationale", "expected_effect", "chosen_at"),
        required=("segment_id", "kind", "rationale", "expected_effect"),
        returns="The recorded Strategy, or an error naming the unmet condition.",
        stage="6",
    ),
    ToolName.GET_STRATEGY.value: ToolSpec(
        name="get_strategy",
        summary="Get a single strategy by ID.",
        effect=_derive_effect("get_strategy"),
        arguments=("strategy_id",),
        required=("strategy_id",),
        returns="The Strategy, or an error string if not found.",
        stage="6",
    ),
    ToolName.LIST_STRATEGIES.value: ToolSpec(
        name="list_strategies",
        summary="List strategies, optionally filtered by segment.",
        effect=_derive_effect("list_strategies"),
        arguments=("segment_id", "limit", "offset"),
        required=(),
        returns="The strategies in creation order.",
        stage="6",
    ),
    ToolName.GET_ODI_SCHEMA.value: ToolSpec(
        name="get_odi_schema",
        summary="Get the canonical JSON schema for all ODI entities.",
        effect=_derive_effect("get_odi_schema"),
        arguments=(),
        returns="The full JSON schema object.",
    ),
    ToolName.COMPUTE_OPPORTUNITY.value: ToolSpec(
        name="compute_opportunity",
        summary="Compute an ODI opportunity score from importance and satisfaction.",
        effect=_derive_effect("compute_opportunity"),
        arguments=("importance", "satisfaction"),
        required=("importance", "satisfaction"),
        returns="The opportunity score as a float.",
        stage="4",
    ),
    ToolName.GET_FRAMEWORK_GUIDELINES.value: ToolSpec(
        name="get_odi_framework_guidelines",
        summary="Get the stage-by-stage ODI framework guide.",
        effect=_derive_effect("get_odi_framework_guidelines"),
        arguments=(),
        returns="The guidelines text.",
    ),
    ToolName.GET_CAPABILITIES.value: ToolSpec(
        name="get_capabilities",
        summary="Get a human-readable list of all available tools.",
        effect=_derive_effect("get_capabilities"),
        arguments=(),
        returns="A grouped summary of every tool.",
    ),
    ToolName.GET_CAPABILITIES_MANIFEST.value: ToolSpec(
        name="get_capabilities_manifest",
        summary="Get a machine-readable manifest of all tools.",
        effect=_derive_effect("get_capabilities_manifest"),
        arguments=(),
        returns="The full tool manifest JSON.",
    ),
    ToolName.GET_HEALTH.value: ToolSpec(
        name="get_health",
        summary="Check that the ODI store is reachable.",
        effect=_derive_effect("get_health"),
        arguments=(),
        returns='{"status": "ok", "store": "accessible"} or a degraded status.',
    ),
    ToolName.LIST_SIGNALS.value: ToolSpec(
        name="list_signals",
        summary="List signals the store recorded — real changes worth attention.",
        effect=_derive_effect("list_signals"),
        arguments=("unread_only", "limit"),
        returns="A list of Signals, newest first.",
    ),
    ToolName.MARK_SIGNAL_READ.value: ToolSpec(
        name="mark_signal_read",
        summary="Mark a signal as read so it stops counting toward the unread badge.",
        effect=_derive_effect("mark_signal_read"),
        arguments=("signal_id",),
        required=("signal_id",),
        returns="The updated Signal.",
    ),
    ToolName.DISMISS_SIGNAL.value: ToolSpec(
        name="dismiss_signal",
        summary="Dismiss a signal; it stays recorded but leaves the feed.",
        effect=_derive_effect("dismiss_signal"),
        arguments=("signal_id",),
        required=("signal_id",),
        returns="The updated Signal.",
    ),
    ToolName.SCHEDULE_WORK.value: ToolSpec(
        name="schedule_work",
        summary="Schedule agent work with a cron or one-shot expression.",
        effect=_derive_effect("schedule_work"),
        arguments=("name", "schedule_expression", "agent_id", "trigger_type", "payload", "job_id"),
        required=("name", "schedule_expression"),
        returns="The created scheduled work item.",
    ),
    ToolName.GET_SCHEDULED_WORK.value: ToolSpec(
        name="get_scheduled_work",
        summary="Get a scheduled work item by ID.",
        effect=_derive_effect("get_scheduled_work"),
        arguments=("work_id",),
        required=("work_id",),
        returns="The scheduled work item, or an error string if not found.",
    ),
    ToolName.LIST_SCHEDULED_WORK.value: ToolSpec(
        name="list_scheduled_work",
        summary="List scheduled work, optionally filtered by Job or status.",
        effect=_derive_effect("list_scheduled_work"),
        arguments=("job_id", "status"),
        returns="A list of scheduled work items.",
    ),
    ToolName.CANCEL_SCHEDULED_WORK.value: ToolSpec(
        name="cancel_scheduled_work",
        summary="Cancel a scheduled work item.",
        effect=_derive_effect("cancel_scheduled_work"),
        arguments=("work_id",),
        required=("work_id",),
        returns="The cancelled scheduled work item.",
    ),
    ToolName.TRIGGER_SCHEDULED_WORK.value: ToolSpec(
        name="trigger_scheduled_work",
        summary="Dispatch a scheduled work item immediately.",
        effect=_derive_effect("trigger_scheduled_work"),
        arguments=("work_id",),
        required=("work_id",),
        returns="The dispatched scheduled work item.",
    ),
}

TOOL_NAMES: tuple[str, ...] = tuple(TOOL_SPECS)

_STAGE_NAMES: dict[str | None, str] = {
    "1": "Stage 1: Define Intent (Job-to-be-Done)",
    "2": "Stage 2: Capture Desired Outcomes",
    "3": "Stage 3: Build the Job Map",
    "4": "Stage 4: Calculate Opportunity Scores",
    "6": "Stage 6: Formulate the Innovation Strategy",
    None: "Supporting Tools",
}

_EFFECT_ORDER: tuple[ToolEffect, ...] = (
    ToolEffect.READ,
    ToolEffect.WRITE,
    ToolEffect.DESTRUCTIVE,
)

_STAGE_ORDER: tuple[str | None, ...] = ("1", "2", "3", "4", "6", None)


def capability_manifest() -> dict:
    """A complete, generated description of the tool surface.

    Every tool in :data:`TOOL_SPECS` appears exactly once.
    """
    return {
        "tools": [
            {
                "name": spec.name,
                "summary": spec.summary,
                "effect": spec.effect.value,
                "arguments": spec.arguments,
                "required": spec.required,
                "returns": spec.returns,
                "stage": spec.stage,
            }
            for spec in TOOL_SPECS.values()
        ]
    }


def capability_summary() -> str:
    """The human-readable rendering, used by ``get_capabilities``.

    Groups tools by effect, then by ODI stage. Names every tool; generated,
    not hand-written.
    """
    by_effect: dict[ToolEffect, dict[str | None, list[ToolSpec]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for spec in TOOL_SPECS.values():
        by_effect[spec.effect][spec.stage].append(spec)

    lines: list[str] = [
        "Here is what I can help you with as your Agentic ODI assistant:",
        "",
    ]

    for effect in _EFFECT_ORDER:
        lines.append(f"## {effect.value.capitalize()} Tools")
        lines.append("")
        for stage in _STAGE_ORDER:
            tools = sorted(by_effect[effect].get(stage, []), key=lambda s: s.name)
            if not tools:
                continue
            lines.append(f"### {_STAGE_NAMES[stage]}")
            lines.append("")
            for spec in tools:
                lines.append(f"- **`{spec.name}`**: {spec.summary}")
            lines.append("")

    return "\n".join(lines)
