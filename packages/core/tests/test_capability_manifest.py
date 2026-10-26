"""Tests for capability manifest generation and drift prevention."""

from __future__ import annotations

import pytest
from agentic_odi_core.contract import (
    TOOL_SPECS,
    ToolEffect,
    capability_manifest,
    capability_summary,
)
from agentic_odi_mcp_server.mcp_server import mcp
from fastmcp import Client
from inline_snapshot import snapshot


def test_capability_summary_contains_all_tools() -> None:
    summary = capability_summary()
    for name in TOOL_SPECS:
        assert name in summary, f"Tool {name} missing from capability_summary()"


def test_capability_manifest_contains_all_tools() -> None:
    manifest = capability_manifest()
    tools = manifest.get("tools", {})
    assert set(tools.keys()) == set(TOOL_SPECS.keys())


@pytest.mark.asyncio
async def test_manifest_and_mcp_registry_have_matching_tool_names() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    mcp_names = {tool.name for tool in tools}
    manifest_names = set(capability_manifest()["tools"].keys())
    assert mcp_names == manifest_names


def test_every_tool_has_nonempty_metadata() -> None:
    manifest = capability_manifest()
    for name, spec in manifest["tools"].items():
        assert spec["summary"].strip(), f"Summary for {name} is empty"
        assert spec["effect"] in {e.value for e in ToolEffect}, f"Invalid effect for {name}"
        assert spec["returns"].strip(), f"Returns for {name} is empty"


def test_tool_effect_derivation_from_name() -> None:
    """Assert effect follows naming conventions so read/write/destructive aren't assigned accidentally."""
    for name, spec in TOOL_SPECS.items():
        if name.startswith("get_") or name.startswith("list_"):
            expected = ToolEffect.READ
        elif name.startswith("delete_"):
            expected = ToolEffect.DESTRUCTIVE
        else:
            expected = ToolEffect.WRITE

        assert spec.effect == expected, f"Tool {name} has effect {spec.effect}, expected {expected}"


def test_capability_manifest_snapshot() -> None:
    manifest = capability_manifest()
    assert manifest == snapshot(
        {
            "tools": {
                "add_job": {
                    "name": "add_job",
                    "summary": "Create a new Job-to-be-Done",
                    "effect": "write",
                    "arguments": ["name", "description"],
                    "required": ["name"],
                    "returns": "Created Job entity in JSON format",
                    "stage": "1",
                },
                "get_jobs": {
                    "name": "get_jobs",
                    "summary": "List all existing Jobs-to-be-Done",
                    "effect": "read",
                    "arguments": ["limit", "offset"],
                    "required": [],
                    "returns": "Array of Job entities in JSON format",
                    "stage": "1",
                },
                "get_job": {
                    "name": "get_job",
                    "summary": "Retrieve a specific Job-to-be-Done by ID",
                    "effect": "read",
                    "arguments": ["job_id"],
                    "required": ["job_id"],
                    "returns": "Job entity in JSON format",
                    "stage": "1",
                },
                "update_job": {
                    "name": "update_job",
                    "summary": "Update an existing Job-to-be-Done",
                    "effect": "write",
                    "arguments": ["job_id", "name", "description"],
                    "required": ["job_id"],
                    "returns": "Updated Job entity in JSON format",
                    "stage": "1",
                },
                "delete_job": {
                    "name": "delete_job",
                    "summary": "Delete a Job-to-be-Done by ID",
                    "effect": "destructive",
                    "arguments": ["job_id"],
                    "required": ["job_id"],
                    "returns": "Confirmation message with deleted Job ID",
                    "stage": "1",
                },
                "add_step": {
                    "name": "add_step",
                    "summary": "Add a process step to a Job Map",
                    "effect": "write",
                    "arguments": ["job_id", "name", "order"],
                    "required": ["job_id", "name", "order"],
                    "returns": "Created Step entity in JSON format",
                    "stage": "4",
                },
                "get_job_map": {
                    "name": "get_job_map",
                    "summary": "Get ordered process steps forming a Job Map",
                    "effect": "read",
                    "arguments": ["job_id", "limit", "offset"],
                    "required": ["job_id"],
                    "returns": "Array of Step entities in JSON format",
                    "stage": "4",
                },
                "get_step": {
                    "name": "get_step",
                    "summary": "Retrieve a specific process step by ID",
                    "effect": "read",
                    "arguments": ["step_id"],
                    "required": ["step_id"],
                    "returns": "Step entity in JSON format",
                    "stage": "4",
                },
                "update_step": {
                    "name": "update_step",
                    "summary": "Update a process step's name or order",
                    "effect": "write",
                    "arguments": ["step_id", "name", "order"],
                    "required": ["step_id"],
                    "returns": "Updated Step entity in JSON format",
                    "stage": "4",
                },
                "delete_step": {
                    "name": "delete_step",
                    "summary": "Delete a process step by ID",
                    "effect": "destructive",
                    "arguments": ["step_id"],
                    "required": ["step_id"],
                    "returns": "Confirmation message with deleted Step ID",
                    "stage": "4",
                },
                "add_outcome": {
                    "name": "add_outcome",
                    "summary": "Record a desired outcome statement with importance/satisfaction",
                    "effect": "write",
                    "arguments": ["job_id", "statement", "importance", "satisfaction", "step_id"],
                    "required": ["job_id", "statement"],
                    "returns": "Created Outcome entity in JSON format",
                    "stage": "2",
                },
                "get_outcomes": {
                    "name": "get_outcomes",
                    "summary": "List desired outcomes for a job with opportunity scores",
                    "effect": "read",
                    "arguments": ["job_id", "step_id", "limit", "offset"],
                    "required": ["job_id"],
                    "returns": "Array of Outcome entities in JSON format",
                    "stage": "2",
                },
                "get_outcome": {
                    "name": "get_outcome",
                    "summary": "Retrieve a specific desired outcome by ID",
                    "effect": "read",
                    "arguments": ["outcome_id"],
                    "required": ["outcome_id"],
                    "returns": "Outcome entity in JSON format",
                    "stage": "2",
                },
                "update_outcome": {
                    "name": "update_outcome",
                    "summary": "Update a desired outcome statement or scores",
                    "effect": "write",
                    "arguments": [
                        "outcome_id",
                        "statement",
                        "importance",
                        "satisfaction",
                        "step_id",
                    ],
                    "required": ["outcome_id"],
                    "returns": "Updated Outcome entity in JSON format",
                    "stage": "2",
                },
                "delete_outcome": {
                    "name": "delete_outcome",
                    "summary": "Delete a desired outcome by ID",
                    "effect": "destructive",
                    "arguments": ["outcome_id"],
                    "required": ["outcome_id"],
                    "returns": "Confirmation message with deleted Outcome ID",
                    "stage": "2",
                },
                "add_customer_outcome": {
                    "name": "add_customer_outcome",
                    "summary": "Capture an ODI-aligned customer outcome linking customer and business value",
                    "effect": "write",
                    "arguments": ["job_id", "customer_value", "business_value", "step_id"],
                    "required": ["job_id", "customer_value", "business_value"],
                    "returns": "Created CustomerOutcome entity in JSON format",
                    "stage": "2",
                },
                "get_customer_outcome": {
                    "name": "get_customer_outcome",
                    "summary": "Retrieve a specific customer outcome by ID",
                    "effect": "read",
                    "arguments": ["outcome_id"],
                    "required": ["outcome_id"],
                    "returns": "CustomerOutcome entity in JSON format",
                    "stage": "2",
                },
                "list_customer_outcomes": {
                    "name": "list_customer_outcomes",
                    "summary": "List customer outcomes for a job",
                    "effect": "read",
                    "arguments": ["job_id", "limit", "offset"],
                    "required": [],
                    "returns": "Array of CustomerOutcome entities in JSON format",
                    "stage": "2",
                },
                "update_customer_outcome": {
                    "name": "update_customer_outcome",
                    "summary": "Update fields on a customer outcome entity",
                    "effect": "write",
                    "arguments": [
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
                    ],
                    "required": ["outcome_id"],
                    "returns": "Updated CustomerOutcome entity in JSON format",
                    "stage": "2",
                },
                "delete_customer_outcome": {
                    "name": "delete_customer_outcome",
                    "summary": "Delete a customer outcome by ID",
                    "effect": "destructive",
                    "arguments": ["outcome_id"],
                    "required": ["outcome_id"],
                    "returns": "Confirmation message with deleted CustomerOutcome ID",
                    "stage": "2",
                },
                "add_evidence": {
                    "name": "add_evidence",
                    "summary": "Capture customer research or interview evidence",
                    "effect": "write",
                    "arguments": [
                        "source_name",
                        "source_kind",
                        "name",
                        "content",
                        "item_type",
                        "raw",
                        "job_id",
                        "step_id",
                        "outcome_id",
                    ],
                    "required": ["source_name", "source_kind", "name", "content"],
                    "returns": "Created Evidence entity in JSON format",
                    "stage": None,
                },
                "get_evidence": {
                    "name": "get_evidence",
                    "summary": "Retrieve a specific evidence record by ID",
                    "effect": "read",
                    "arguments": ["evidence_id"],
                    "required": ["evidence_id"],
                    "returns": "Evidence entity in JSON format",
                    "stage": None,
                },
                "list_evidence": {
                    "name": "list_evidence",
                    "summary": "List evidence records filtered by job, step, or outcome",
                    "effect": "read",
                    "arguments": ["job_id", "step_id", "outcome_id", "limit", "offset"],
                    "required": [],
                    "returns": "Array of Evidence entities in JSON format",
                    "stage": None,
                },
                "delete_evidence": {
                    "name": "delete_evidence",
                    "summary": "Delete an evidence record by ID",
                    "effect": "destructive",
                    "arguments": ["evidence_id"],
                    "required": ["evidence_id"],
                    "returns": "Confirmation message with deleted Evidence ID",
                    "stage": None,
                },
                "promote_evidence": {
                    "name": "promote_evidence",
                    "summary": "Promote research evidence into a Job or desired Outcome",
                    "effect": "write",
                    "arguments": [
                        "evidence_id",
                        "target",
                        "job_id",
                        "statement",
                        "name",
                        "importance",
                        "satisfaction",
                    ],
                    "required": ["evidence_id", "target"],
                    "returns": "Promoted Job or Outcome entity in JSON format",
                    "stage": None,
                },
                "evaluate_outcome": {
                    "name": "evaluate_outcome",
                    "summary": "Validate an outcome statement against canonical ODI formatting guidelines",
                    "effect": "write",
                    "arguments": ["statement", "job_id"],
                    "required": ["statement"],
                    "returns": "Evaluation result with verdict, issues, and suggestions in JSON format",
                    "stage": "2",
                },
                "get_odi_schema": {
                    "name": "get_odi_schema",
                    "summary": "Get canonical JSON schema definitions for all ODI entities",
                    "effect": "read",
                    "arguments": [],
                    "required": [],
                    "returns": "JSON schema dictionary",
                    "stage": None,
                },
                "compute_opportunity": {
                    "name": "compute_opportunity",
                    "summary": "Calculate the ODI Opportunity Score from importance and satisfaction",
                    "effect": "write",
                    "arguments": ["importance", "satisfaction"],
                    "required": ["importance", "satisfaction"],
                    "returns": "Calculated opportunity score string",
                    "stage": "3",
                },
                "get_odi_framework_guidelines": {
                    "name": "get_odi_framework_guidelines",
                    "summary": "Retrieve stage-by-stage ODI methodology guidelines",
                    "effect": "read",
                    "arguments": [],
                    "required": [],
                    "returns": "Stage-by-stage framework guide text",
                    "stage": None,
                },
                "get_capabilities": {
                    "name": "get_capabilities",
                    "summary": "Get human-readable capabilities summary of all available tools",
                    "effect": "read",
                    "arguments": [],
                    "required": [],
                    "returns": "Human-readable summary of tools and capabilities",
                    "stage": None,
                },
                "get_capabilities_manifest": {
                    "name": "get_capabilities_manifest",
                    "summary": "Get structured JSON manifest of all available tools",
                    "effect": "read",
                    "arguments": [],
                    "required": [],
                    "returns": "Machine-readable capability manifest in JSON format",
                    "stage": None,
                },
            }
        }
    )
