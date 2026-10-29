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
    EVALUATE_OUTCOME = "evaluate_outcome"
    GET_ODI_SCHEMA = "get_odi_schema"
    COMPUTE_OPPORTUNITY = "compute_opportunity"
    GET_FRAMEWORK_GUIDELINES = "get_odi_framework_guidelines"
    GET_CAPABILITIES = "get_capabilities"
    GET_CAPABILITIES_MANIFEST = "get_capabilities_manifest"
    LIST_SIGNALS = "list_signals"
    MARK_SIGNAL_READ = "mark_signal_read"
    DISMISS_SIGNAL = "dismiss_signal"
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

    get_*/list_* → READ, delete_* → DESTRUCTIVE, everything else → WRITE.
    """
    if name.startswith(("get_", "list_")):
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
        arguments=("job_id", "statement", "importance", "satisfaction", "step_id"),
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
        arguments=("outcome_id", "statement", "importance", "satisfaction", "step_id"),
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
    None: "Supporting Tools",
}

_EFFECT_ORDER: tuple[ToolEffect, ...] = (
    ToolEffect.READ,
    ToolEffect.WRITE,
    ToolEffect.DESTRUCTIVE,
)

_STAGE_ORDER: tuple[str | None, ...] = ("1", "2", "3", "4", None)


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
