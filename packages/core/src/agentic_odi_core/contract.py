"""Single source of truth for the MCP tool surface.

Adapters must use :class:`ToolName` instead of hard-coded strings, and the
contract test in ``tests/contract`` asserts that the live FastMCP registry
matches :data:`TOOL_SPECS`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolEffect(str, Enum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


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


@dataclass(frozen=True)
class ToolSpec:
    """Metadata describing a tool on the Agentic ODI tool surface."""

    name: str
    summary: str
    effect: ToolEffect
    arguments: tuple[str, ...] = field(default_factory=tuple)
    required: tuple[str, ...] = field(default_factory=tuple)
    returns: str = ""
    stage: str | None = None


TOOL_SPECS: dict[str, ToolSpec] = {
    ToolName.ADD_JOB.value: ToolSpec(
        name=ToolName.ADD_JOB.value,
        summary="Create a new Job-to-be-Done",
        effect=ToolEffect.WRITE,
        arguments=("name", "description"),
        required=("name",),
        returns="Created Job entity in JSON format",
        stage="1",
    ),
    ToolName.GET_JOBS.value: ToolSpec(
        name=ToolName.GET_JOBS.value,
        summary="List all existing Jobs-to-be-Done",
        effect=ToolEffect.READ,
        arguments=(),
        required=(),
        returns="Array of Job entities in JSON format",
        stage="1",
    ),
    ToolName.GET_JOB.value: ToolSpec(
        name=ToolName.GET_JOB.value,
        summary="Retrieve a specific Job-to-be-Done by ID",
        effect=ToolEffect.READ,
        arguments=("job_id",),
        required=("job_id",),
        returns="Job entity in JSON format",
        stage="1",
    ),
    ToolName.UPDATE_JOB.value: ToolSpec(
        name=ToolName.UPDATE_JOB.value,
        summary="Update an existing Job-to-be-Done",
        effect=ToolEffect.WRITE,
        arguments=("job_id", "name", "description"),
        required=("job_id",),
        returns="Updated Job entity in JSON format",
        stage="1",
    ),
    ToolName.DELETE_JOB.value: ToolSpec(
        name=ToolName.DELETE_JOB.value,
        summary="Delete a Job-to-be-Done by ID",
        effect=ToolEffect.DESTRUCTIVE,
        arguments=("job_id",),
        required=("job_id",),
        returns="Confirmation message with deleted Job ID",
        stage="1",
    ),
    ToolName.ADD_STEP.value: ToolSpec(
        name=ToolName.ADD_STEP.value,
        summary="Add a process step to a Job Map",
        effect=ToolEffect.WRITE,
        arguments=("job_id", "name", "order"),
        required=("job_id", "name", "order"),
        returns="Created Step entity in JSON format",
        stage="4",
    ),
    ToolName.GET_JOB_MAP.value: ToolSpec(
        name=ToolName.GET_JOB_MAP.value,
        summary="Get ordered process steps forming a Job Map",
        effect=ToolEffect.READ,
        arguments=("job_id",),
        required=("job_id",),
        returns="Array of Step entities in JSON format",
        stage="4",
    ),
    ToolName.GET_STEP.value: ToolSpec(
        name=ToolName.GET_STEP.value,
        summary="Retrieve a specific process step by ID",
        effect=ToolEffect.READ,
        arguments=("step_id",),
        required=("step_id",),
        returns="Step entity in JSON format",
        stage="4",
    ),
    ToolName.UPDATE_STEP.value: ToolSpec(
        name=ToolName.UPDATE_STEP.value,
        summary="Update a process step's name or order",
        effect=ToolEffect.WRITE,
        arguments=("step_id", "name", "order"),
        required=("step_id",),
        returns="Updated Step entity in JSON format",
        stage="4",
    ),
    ToolName.DELETE_STEP.value: ToolSpec(
        name=ToolName.DELETE_STEP.value,
        summary="Delete a process step by ID",
        effect=ToolEffect.DESTRUCTIVE,
        arguments=("step_id",),
        required=("step_id",),
        returns="Confirmation message with deleted Step ID",
        stage="4",
    ),
    ToolName.ADD_OUTCOME.value: ToolSpec(
        name=ToolName.ADD_OUTCOME.value,
        summary="Record a desired outcome statement with importance/satisfaction",
        effect=ToolEffect.WRITE,
        arguments=("job_id", "statement", "importance", "satisfaction", "step_id"),
        required=("job_id", "statement"),
        returns="Created Outcome entity in JSON format",
        stage="2",
    ),
    ToolName.GET_OUTCOMES.value: ToolSpec(
        name=ToolName.GET_OUTCOMES.value,
        summary="List desired outcomes for a job with opportunity scores",
        effect=ToolEffect.READ,
        arguments=("job_id", "step_id"),
        required=("job_id",),
        returns="Array of Outcome entities in JSON format",
        stage="2",
    ),
    ToolName.GET_OUTCOME.value: ToolSpec(
        name=ToolName.GET_OUTCOME.value,
        summary="Retrieve a specific desired outcome by ID",
        effect=ToolEffect.READ,
        arguments=("outcome_id",),
        required=("outcome_id",),
        returns="Outcome entity in JSON format",
        stage="2",
    ),
    ToolName.UPDATE_OUTCOME.value: ToolSpec(
        name=ToolName.UPDATE_OUTCOME.value,
        summary="Update a desired outcome statement or scores",
        effect=ToolEffect.WRITE,
        arguments=("outcome_id", "statement", "importance", "satisfaction", "step_id"),
        required=("outcome_id",),
        returns="Updated Outcome entity in JSON format",
        stage="2",
    ),
    ToolName.DELETE_OUTCOME.value: ToolSpec(
        name=ToolName.DELETE_OUTCOME.value,
        summary="Delete a desired outcome by ID",
        effect=ToolEffect.DESTRUCTIVE,
        arguments=("outcome_id",),
        required=("outcome_id",),
        returns="Confirmation message with deleted Outcome ID",
        stage="2",
    ),
    ToolName.ADD_CUSTOMER_OUTCOME.value: ToolSpec(
        name=ToolName.ADD_CUSTOMER_OUTCOME.value,
        summary="Capture an ODI-aligned customer outcome linking customer and business value",
        effect=ToolEffect.WRITE,
        arguments=("job_id", "customer_value", "business_value", "step_id"),
        required=("job_id", "customer_value", "business_value"),
        returns="Created CustomerOutcome entity in JSON format",
        stage="2",
    ),
    ToolName.GET_CUSTOMER_OUTCOME.value: ToolSpec(
        name=ToolName.GET_CUSTOMER_OUTCOME.value,
        summary="Retrieve a specific customer outcome by ID",
        effect=ToolEffect.READ,
        arguments=("outcome_id",),
        required=("outcome_id",),
        returns="CustomerOutcome entity in JSON format",
        stage="2",
    ),
    ToolName.LIST_CUSTOMER_OUTCOMES.value: ToolSpec(
        name=ToolName.LIST_CUSTOMER_OUTCOMES.value,
        summary="List customer outcomes for a job",
        effect=ToolEffect.READ,
        arguments=("job_id",),
        required=(),
        returns="Array of CustomerOutcome entities in JSON format",
        stage="2",
    ),
    ToolName.UPDATE_CUSTOMER_OUTCOME.value: ToolSpec(
        name=ToolName.UPDATE_CUSTOMER_OUTCOME.value,
        summary="Update fields on a customer outcome entity",
        effect=ToolEffect.WRITE,
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
        returns="Updated CustomerOutcome entity in JSON format",
        stage="2",
    ),
    ToolName.DELETE_CUSTOMER_OUTCOME.value: ToolSpec(
        name=ToolName.DELETE_CUSTOMER_OUTCOME.value,
        summary="Delete a customer outcome by ID",
        effect=ToolEffect.DESTRUCTIVE,
        arguments=("outcome_id",),
        required=("outcome_id",),
        returns="Confirmation message with deleted CustomerOutcome ID",
        stage="2",
    ),
    ToolName.ADD_EVIDENCE.value: ToolSpec(
        name=ToolName.ADD_EVIDENCE.value,
        summary="Capture customer research or interview evidence",
        effect=ToolEffect.WRITE,
        arguments=(
            "source_name",
            "source_kind",
            "name",
            "content",
            "item_type",
            "raw",
            "job_id",
            "step_id",
            "outcome_id",
        ),
        required=("source_name", "source_kind", "name", "content"),
        returns="Created Evidence entity in JSON format",
        stage=None,
    ),
    ToolName.GET_EVIDENCE.value: ToolSpec(
        name=ToolName.GET_EVIDENCE.value,
        summary="Retrieve a specific evidence record by ID",
        effect=ToolEffect.READ,
        arguments=("evidence_id",),
        required=("evidence_id",),
        returns="Evidence entity in JSON format",
        stage=None,
    ),
    ToolName.LIST_EVIDENCE.value: ToolSpec(
        name=ToolName.LIST_EVIDENCE.value,
        summary="List evidence records filtered by job, step, or outcome",
        effect=ToolEffect.READ,
        arguments=("job_id", "step_id", "outcome_id"),
        required=(),
        returns="Array of Evidence entities in JSON format",
        stage=None,
    ),
    ToolName.DELETE_EVIDENCE.value: ToolSpec(
        name=ToolName.DELETE_EVIDENCE.value,
        summary="Delete an evidence record by ID",
        effect=ToolEffect.DESTRUCTIVE,
        arguments=("evidence_id",),
        required=("evidence_id",),
        returns="Confirmation message with deleted Evidence ID",
        stage=None,
    ),
    ToolName.PROMOTE_EVIDENCE.value: ToolSpec(
        name=ToolName.PROMOTE_EVIDENCE.value,
        summary="Promote research evidence into a Job or desired Outcome",
        effect=ToolEffect.WRITE,
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
        returns="Promoted Job or Outcome entity in JSON format",
        stage=None,
    ),
    ToolName.EVALUATE_OUTCOME.value: ToolSpec(
        name=ToolName.EVALUATE_OUTCOME.value,
        summary="Validate an outcome statement against canonical ODI formatting guidelines",
        effect=ToolEffect.WRITE,
        arguments=("statement", "job_id"),
        required=("statement",),
        returns="Evaluation result with verdict, issues, and suggestions in JSON format",
        stage="2",
    ),
    ToolName.GET_ODI_SCHEMA.value: ToolSpec(
        name=ToolName.GET_ODI_SCHEMA.value,
        summary="Get canonical JSON schema definitions for all ODI entities",
        effect=ToolEffect.READ,
        arguments=(),
        required=(),
        returns="JSON schema dictionary",
        stage=None,
    ),
    ToolName.COMPUTE_OPPORTUNITY.value: ToolSpec(
        name=ToolName.COMPUTE_OPPORTUNITY.value,
        summary="Calculate the ODI Opportunity Score from importance and satisfaction",
        effect=ToolEffect.WRITE,
        arguments=("importance", "satisfaction"),
        required=("importance", "satisfaction"),
        returns="Calculated opportunity score string",
        stage="3",
    ),
    ToolName.GET_FRAMEWORK_GUIDELINES.value: ToolSpec(
        name=ToolName.GET_FRAMEWORK_GUIDELINES.value,
        summary="Retrieve stage-by-stage ODI methodology guidelines",
        effect=ToolEffect.READ,
        arguments=(),
        required=(),
        returns="Stage-by-stage framework guide text",
        stage=None,
    ),
    ToolName.GET_CAPABILITIES.value: ToolSpec(
        name=ToolName.GET_CAPABILITIES.value,
        summary="Get human-readable capabilities summary of all available tools",
        effect=ToolEffect.READ,
        arguments=(),
        required=(),
        returns="Human-readable summary of tools and capabilities",
        stage=None,
    ),
    ToolName.GET_CAPABILITIES_MANIFEST.value: ToolSpec(
        name=ToolName.GET_CAPABILITIES_MANIFEST.value,
        summary="Get structured JSON manifest of all available tools",
        effect=ToolEffect.READ,
        arguments=(),
        required=(),
        returns="Machine-readable capability manifest in JSON format",
        stage=None,
    ),
}

TOOL_NAMES: tuple[str, ...] = tuple(TOOL_SPECS)


def capability_manifest() -> dict[str, Any]:
    """A complete, generated description of the tool surface."""
    return {
        "tools": {
            spec.name: {
                "name": spec.name,
                "summary": spec.summary,
                "effect": spec.effect.value,
                "arguments": list(spec.arguments),
                "required": list(spec.required),
                "returns": spec.returns,
                "stage": spec.stage,
            }
            for spec in TOOL_SPECS.values()
        }
    }


def capability_summary() -> str:
    """The human-readable rendering, used by get_capabilities."""
    stage_titles: dict[str | None, str] = {
        "1": "Stage 1: Define Intent (Jobs-to-be-Done)",
        "2": "Stage 2: Capture & Evaluate Desired Outcomes",
        "3": "Stage 3: Calculate Opportunity Scores",
        "4": "Stage 4: Build Job Maps",
        None: "General & Supporting Capabilities",
    }

    lines = [
        "Here is what I can help you with as your Agentic ODI assistant:",
        "",
    ]

    stages: list[str | None] = ["1", "2", "3", "4", None]

    for stage in stages:
        title = stage_titles[stage]
        stage_tools = [spec for spec in TOOL_SPECS.values() if spec.stage == stage]
        if not stage_tools:
            continue
        lines.append(f"### {title}")

        for effect in (ToolEffect.READ, ToolEffect.WRITE, ToolEffect.DESTRUCTIVE):
            effect_tools = [t for t in stage_tools if t.effect == effect]
            if not effect_tools:
                continue
            effect_label = effect.value.upper()
            lines.append(f"- **{effect_label}**:")
            for tool in effect_tools:
                args_str = f"({', '.join(tool.arguments)})" if tool.arguments else "()"
                lines.append(f"  - `{tool.name}{args_str}`: {tool.summary}")
        lines.append("")

    lines.append(
        "💡 **Tip**: Ask me to 'get started' and I will guide you step-by-step through the ODI process!"
    )
    return "\n".join(lines).strip()
