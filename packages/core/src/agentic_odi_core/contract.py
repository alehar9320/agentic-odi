"""Single source of truth for the MCP tool surface.

Adapters must use :class:`ToolName` instead of hard-coded strings, and the
contract test in ``tests/contract`` asserts that the live FastMCP registry
matches :data:`TOOL_SPECS`.
"""

from __future__ import annotations

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


@dataclass(frozen=True)
class ToolSpec:
    """Argument names exposed by a tool and the subset that is required."""

    arguments: tuple[str, ...] = field(default_factory=tuple)
    required: tuple[str, ...] = field(default_factory=tuple)


TOOL_SPECS: dict[str, ToolSpec] = {
    ToolName.ADD_JOB.value: ToolSpec(("name", "description"), ("name",)),
    ToolName.GET_JOBS.value: ToolSpec(("limit", "offset")),
    ToolName.GET_JOB.value: ToolSpec(("job_id",), ("job_id",)),
    ToolName.UPDATE_JOB.value: ToolSpec(("job_id", "name", "description"), ("job_id",)),
    ToolName.DELETE_JOB.value: ToolSpec(("job_id",), ("job_id",)),
    ToolName.ADD_STEP.value: ToolSpec(("job_id", "name", "order"), ("job_id", "name", "order")),
    ToolName.GET_JOB_MAP.value: ToolSpec(("job_id", "limit", "offset"), ("job_id",)),
    ToolName.GET_STEP.value: ToolSpec(("step_id",), ("step_id",)),
    ToolName.UPDATE_STEP.value: ToolSpec(("step_id", "name", "order"), ("step_id",)),
    ToolName.DELETE_STEP.value: ToolSpec(("step_id",), ("step_id",)),
    ToolName.ADD_OUTCOME.value: ToolSpec(
        ("job_id", "statement", "importance", "satisfaction", "step_id"),
        ("job_id", "statement"),
    ),
    ToolName.GET_OUTCOMES.value: ToolSpec(("job_id", "step_id", "limit", "offset"), ("job_id",)),
    ToolName.GET_OUTCOME.value: ToolSpec(("outcome_id",), ("outcome_id",)),
    ToolName.UPDATE_OUTCOME.value: ToolSpec(
        ("outcome_id", "statement", "importance", "satisfaction", "step_id"),
        ("outcome_id",),
    ),
    ToolName.DELETE_OUTCOME.value: ToolSpec(("outcome_id",), ("outcome_id",)),
    ToolName.ADD_CUSTOMER_OUTCOME.value: ToolSpec(
        ("job_id", "customer_value", "business_value", "step_id"),
        ("job_id", "customer_value", "business_value"),
    ),
    ToolName.GET_CUSTOMER_OUTCOME.value: ToolSpec(("outcome_id",), ("outcome_id",)),
    ToolName.LIST_CUSTOMER_OUTCOMES.value: ToolSpec(("job_id", "limit", "offset")),
    ToolName.UPDATE_CUSTOMER_OUTCOME.value: ToolSpec(
        (
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
        ("outcome_id",),
    ),
    ToolName.DELETE_CUSTOMER_OUTCOME.value: ToolSpec(("outcome_id",), ("outcome_id",)),
    ToolName.ADD_EVIDENCE.value: ToolSpec(
        (
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
        ("source_name", "source_kind", "name", "content"),
    ),
    ToolName.GET_EVIDENCE.value: ToolSpec(("evidence_id",), ("evidence_id",)),
    ToolName.LIST_EVIDENCE.value: ToolSpec(("job_id", "step_id", "outcome_id", "limit", "offset")),
    ToolName.DELETE_EVIDENCE.value: ToolSpec(("evidence_id",), ("evidence_id",)),
    ToolName.PROMOTE_EVIDENCE.value: ToolSpec(
        (
            "evidence_id",
            "target",
            "job_id",
            "statement",
            "name",
            "importance",
            "satisfaction",
        ),
        ("evidence_id", "target"),
    ),
    ToolName.EVALUATE_OUTCOME.value: ToolSpec(("statement", "job_id"), ("statement",)),
    ToolName.GET_ODI_SCHEMA.value: ToolSpec(),
    ToolName.COMPUTE_OPPORTUNITY.value: ToolSpec(
        ("importance", "satisfaction"), ("importance", "satisfaction")
    ),
    ToolName.GET_FRAMEWORK_GUIDELINES.value: ToolSpec(),
    ToolName.GET_CAPABILITIES.value: ToolSpec(),
}

TOOL_NAMES: tuple[str, ...] = tuple(TOOL_SPECS)
