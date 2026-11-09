"""The published contract, pinned — so a rename fails here instead of in an agent.

Three surfaces are snapshotted together: the declared ``TOOL_SPECS``, the input
schemas the live FastMCP registry actually serves, and ``odi_schema()`` for every
stored entity. Pinning only the declaration would miss the drift that matters
most — the one between what the contract says and what the server sends.

Deliberately re-pin after an intentional contract change::

    uv run pytest tests/contract/test_contract_snapshot.py --inline-snapshot=update

Then read the rewritten literals as code and commit them. CI runs this file with
no ``--inline-snapshot`` flag, so it can never accept drift for you. A change that
is not yours to make is a breaking change, and it needs its own compatibility
decision — not a re-pinned snapshot.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

import pytest
from agentic_odi_core.contract import TOOL_SPECS, ToolSpec
from agentic_odi_core.schema import odi_schema
from agentic_odi_mcp_server.mcp_server import mcp
from fastmcp import Client
from inline_snapshot import Snapshot, get_snapshot_value, snapshot

#: The three surfaces, named the way a failure should name them.
DECLARED = "the declared tool contract"
LIVE = "the live registry's input schemas"
ENTITIES = "the published entity schema"


def _ordered(value: Any) -> Any:
    """Order every mapping by key; lists keep their order, because there it is meaning."""
    if isinstance(value, dict):
        return {key: _ordered(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [_ordered(item) for item in value]
    return value


def _tool_spec_rows(specs: Mapping[str, ToolSpec] = TOOL_SPECS) -> list[dict[str, Any]]:
    """One row per declared tool, ordered by tool name."""
    return [
        {
            "name": spec.name,
            "effect": spec.effect.value,
            "summary": spec.summary,
            "arguments": list(spec.arguments),
            "required": list(spec.required),
            "returns": spec.returns,
            "stage": spec.stage,
        }
        for spec in sorted(specs.values(), key=lambda spec: spec.name)
    ]


def _live_rows(schemas: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    """Every live tool's input schema, ordered by tool name and by key."""
    return {name: _ordered(schemas[name]) for name in sorted(schemas)}


def _entity_rows(schema: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    """Every published entity schema, ordered by entity name and by key."""
    return {name: _ordered(schema[name]) for name in sorted(schema)}


def _drift_path(path: str, key: object) -> str:
    return f"{path}.{key}" if path else str(key)


def _entry_name(value: Any) -> str | None:
    """A list row's name, when it has one — so a drift path reads ``add_job``, not ``[2]``."""
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str):
            return name
    return None


def _drift(path: str, pinned: Any, actual: Any) -> list[str]:
    """Name the entries that moved, and leave everything else out of the message."""
    if isinstance(pinned, dict) and isinstance(actual, dict):
        lines = [
            f"{_drift_path(path, key)}: gone ({pinned[key]!r})"
            for key in sorted(set(pinned) - set(actual), key=str)
        ]
        lines += [
            f"{_drift_path(path, key)}: new ({actual[key]!r})"
            for key in sorted(set(actual) - set(pinned), key=str)
        ]
        for key in sorted(set(pinned) & set(actual), key=str):
            lines += _drift(_drift_path(path, key), pinned[key], actual[key])
        return lines
    if isinstance(pinned, list) and isinstance(actual, list):
        if len(pinned) != len(actual):
            return [f"{path}: {len(pinned)} entries pinned, {len(actual)} now"]
        lines = []
        for index, (before, after) in enumerate(zip(pinned, actual, strict=True)):
            name = _entry_name(before)
            if name is not None and name == _entry_name(after):
                lines += _drift(f"{path}.{name}" if path else name, before, after)
            else:
                lines += _drift(f"{path}[{index}]", before, after)
        return lines
    if pinned != actual:
        return [f"{path}: pinned {pinned!r}, now {actual!r}"]
    return []


def _assert_pinned(surface: str, actual: Any, pinned: Any) -> None:
    """Compare one surface with its pin and, when it moved, say which entries did.

    ``pinned`` is the ``Snapshot`` when this is the gate itself, and a plain value
    when a drift fixture is checking that the pin would notice.
    """
    assert actual == pinned, f"{surface} drifted from its pin:\n" + "\n".join(
        f"  {line}" for line in _drift("", pinned, actual)
    )


def _declared_pin() -> Snapshot:
    return snapshot(
        [
            {
                "name": "add_customer_outcome",
                "effect": "write",
                "summary": "Add a Customer Outcome pairing customer and business value.",
                "arguments": ["job_id", "customer_value", "business_value", "step_id"],
                "required": ["job_id", "customer_value", "business_value"],
                "returns": "The created Customer Outcome.",
                "stage": None,
            },
            {
                "name": "add_evidence",
                "effect": "write",
                "summary": "Capture an evidence record from a connector.",
                "arguments": [
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
                    "origin",
                ],
                "required": ["source_name", "source_kind", "name", "content"],
                "returns": "The created Evidence record.",
                "stage": None,
            },
            {
                "name": "add_job",
                "effect": "write",
                "summary": "Create a new Job-to-be-Done.",
                "arguments": ["name", "description", "origin"],
                "required": ["name"],
                "returns": "The created Job.",
                "stage": "1",
            },
            {
                "name": "add_outcome",
                "effect": "write",
                "summary": "Add a desired Outcome to a Job; three questions and the person's answers come before any score, and the score carries them as a claim_check.",
                "arguments": [
                    "job_id",
                    "statement",
                    "importance",
                    "satisfaction",
                    "step_id",
                    "origin",
                    "claim_check",
                ],
                "required": ["job_id", "statement"],
                "returns": "The created Outcome.",
                "stage": "2",
            },
            {
                "name": "add_step",
                "effect": "write",
                "summary": "Add a step to a Job's job map.",
                "arguments": ["job_id", "name", "order", "stage", "allow_empty_job_map", "origin"],
                "required": ["job_id", "name", "order"],
                "returns": "The created Step.",
                "stage": "3",
            },
            {
                "name": "approve_proposal",
                "effect": "write",
                "summary": "Approve a proposal and write it as an Outcome.",
                "arguments": ["proposal_id", "statement", "importance", "satisfaction"],
                "required": ["proposal_id"],
                "returns": "The created Outcome.",
                "stage": "2",
            },
            {
                "name": "cancel_scheduled_work",
                "effect": "write",
                "summary": "Cancel a scheduled work item.",
                "arguments": ["work_id"],
                "required": ["work_id"],
                "returns": "The cancelled scheduled work item.",
                "stage": None,
            },
            {
                "name": "compute_opportunity",
                "effect": "read",
                "summary": "Compute an ODI opportunity score from importance and satisfaction.",
                "arguments": ["importance", "satisfaction"],
                "required": ["importance", "satisfaction"],
                "returns": "The opportunity score as a float.",
                "stage": "4",
            },
            {
                "name": "delete_customer_outcome",
                "effect": "destructive",
                "summary": "Delete a Customer Outcome.",
                "arguments": ["outcome_id"],
                "required": ["outcome_id"],
                "returns": "The deleted Customer Outcome ID.",
                "stage": None,
            },
            {
                "name": "delete_evidence",
                "effect": "destructive",
                "summary": "Delete an evidence record.",
                "arguments": ["evidence_id"],
                "required": ["evidence_id"],
                "returns": "The deleted Evidence ID.",
                "stage": None,
            },
            {
                "name": "delete_job",
                "effect": "destructive",
                "summary": "Delete a Job and its cascading dependents.",
                "arguments": ["job_id"],
                "required": ["job_id"],
                "returns": "The deleted Job ID.",
                "stage": "1",
            },
            {
                "name": "delete_outcome",
                "effect": "destructive",
                "summary": "Delete a desired Outcome.",
                "arguments": ["outcome_id"],
                "required": ["outcome_id"],
                "returns": "The deleted Outcome ID.",
                "stage": "2",
            },
            {
                "name": "delete_step",
                "effect": "destructive",
                "summary": "Delete a Step and its cascading dependents.",
                "arguments": ["step_id"],
                "required": ["step_id"],
                "returns": "The deleted Step ID.",
                "stage": "3",
            },
            {
                "name": "dismiss_signal",
                "effect": "write",
                "summary": "Dismiss a signal; it stays recorded but leaves the feed.",
                "arguments": ["signal_id"],
                "required": ["signal_id"],
                "returns": "The updated Signal.",
                "stage": None,
            },
            {
                "name": "evaluate_outcome",
                "effect": "read",
                "summary": "Evaluate an outcome statement against ODI format rules.",
                "arguments": ["statement", "job_id"],
                "required": ["statement"],
                "returns": "A verdict with coded issues and suggestions.",
                "stage": "2",
            },
            {
                "name": "get_capabilities",
                "effect": "read",
                "summary": "Get a human-readable list of all available tools.",
                "arguments": [],
                "required": [],
                "returns": "A grouped summary of every tool.",
                "stage": None,
            },
            {
                "name": "get_capabilities_manifest",
                "effect": "read",
                "summary": "Get a machine-readable manifest of all tools.",
                "arguments": [],
                "required": [],
                "returns": "The full tool manifest JSON.",
                "stage": None,
            },
            {
                "name": "get_customer_outcome",
                "effect": "read",
                "summary": "Get a single Customer Outcome by ID.",
                "arguments": ["outcome_id"],
                "required": ["outcome_id"],
                "returns": "The Customer Outcome, or an error string if not found.",
                "stage": None,
            },
            {
                "name": "get_evidence",
                "effect": "read",
                "summary": "Get a single evidence record by ID.",
                "arguments": ["evidence_id"],
                "required": ["evidence_id"],
                "returns": "The Evidence record, or an error string if not found.",
                "stage": None,
            },
            {
                "name": "get_health",
                "effect": "read",
                "summary": "Check that the ODI store is reachable.",
                "arguments": [],
                "required": [],
                "returns": '{"status": "ok", "store": "accessible"} or a degraded status.',
                "stage": None,
            },
            {
                "name": "get_job",
                "effect": "read",
                "summary": "Get a single Job by ID.",
                "arguments": ["job_id"],
                "required": ["job_id"],
                "returns": "The Job, or an error string if not found.",
                "stage": "1",
            },
            {
                "name": "get_job_map",
                "effect": "read",
                "summary": "Get the ordered job map for a Job.",
                "arguments": ["job_id", "limit", "offset"],
                "required": ["job_id"],
                "returns": "A list of Steps ordered by stage.",
                "stage": "3",
            },
            {
                "name": "get_jobs",
                "effect": "read",
                "summary": "List all Jobs.",
                "arguments": ["limit", "offset"],
                "required": [],
                "returns": "A list of Jobs.",
                "stage": "1",
            },
            {
                "name": "get_odi_framework_guidelines",
                "effect": "read",
                "summary": "Get the stage-by-stage ODI framework guide.",
                "arguments": [],
                "required": [],
                "returns": "The guidelines text.",
                "stage": None,
            },
            {
                "name": "get_odi_schema",
                "effect": "read",
                "summary": "Get the canonical JSON schema for all ODI entities.",
                "arguments": [],
                "required": [],
                "returns": "The full JSON schema object.",
                "stage": None,
            },
            {
                "name": "get_outcome",
                "effect": "read",
                "summary": "Get a single Outcome by ID.",
                "arguments": ["outcome_id"],
                "required": ["outcome_id"],
                "returns": "The Outcome, or an error string if not found.",
                "stage": "2",
            },
            {
                "name": "get_outcome_alignments",
                "effect": "read",
                "summary": "List the V2MOM links recorded on Outcomes.",
                "arguments": ["outcome_id"],
                "required": [],
                "returns": "A list of links, each naming the outcome, field, key, and text.",
                "stage": "6",
            },
            {
                "name": "get_outcomes",
                "effect": "read",
                "summary": "List desired Outcomes for a Job.",
                "arguments": ["job_id", "step_id", "limit", "offset", "sort"],
                "required": ["job_id"],
                "returns": "A list of Outcomes.",
                "stage": "2",
            },
            {
                "name": "get_scheduled_work",
                "effect": "read",
                "summary": "Get a scheduled work item by ID.",
                "arguments": ["work_id"],
                "required": ["work_id"],
                "returns": "The scheduled work item, or an error string if not found.",
                "stage": None,
            },
            {
                "name": "get_segments",
                "effect": "read",
                "summary": "List the segments the market was divided into.",
                "arguments": ["job_id"],
                "required": [],
                "returns": "A list of Segments. Empty until segment_market has run.",
                "stage": "5",
            },
            {
                "name": "get_step",
                "effect": "read",
                "summary": "Get a single Step by ID.",
                "arguments": ["step_id"],
                "required": ["step_id"],
                "returns": "The Step, or an error string if not found.",
                "stage": "3",
            },
            {
                "name": "get_strategy",
                "effect": "read",
                "summary": "Get the most recently recorded innovation strategy.",
                "arguments": [],
                "required": [],
                "returns": "The Strategy with its rejected alternatives, or null if none was recorded.",
                "stage": "6",
            },
            {
                "name": "get_traceability_report",
                "effect": "read",
                "summary": "Report orphans, unfunded objectives, and links the vision dropped.",
                "arguments": [],
                "required": [],
                "returns": "The orphans, unfunded, and drift lists, or a note that no objectives exist.",
                "stage": "6",
            },
            {
                "name": "link_outcome",
                "effect": "write",
                "summary": "Link an Outcome to the V2MOM method or measure it advances.",
                "arguments": ["outcome_id", "field", "text"],
                "required": ["outcome_id", "field", "text"],
                "returns": "The updated Outcome, or a refusal naming the objectives that do exist.",
                "stage": "6",
            },
            {
                "name": "list_customer_outcomes",
                "effect": "read",
                "summary": "List Customer Outcomes for a Job.",
                "arguments": ["job_id", "limit", "offset"],
                "required": [],
                "returns": "A list of Customer Outcomes.",
                "stage": None,
            },
            {
                "name": "list_evidence",
                "effect": "read",
                "summary": "List evidence records, optionally filtered by job/step/outcome.",
                "arguments": ["job_id", "step_id", "outcome_id", "limit", "offset"],
                "required": [],
                "returns": "A list of Evidence records.",
                "stage": None,
            },
            {
                "name": "list_proposals",
                "effect": "read",
                "summary": "List outcome proposals, optionally filtered by status.",
                "arguments": ["status"],
                "required": [],
                "returns": "A list of OutcomeProposals.",
                "stage": "2",
            },
            {
                "name": "list_scheduled_work",
                "effect": "read",
                "summary": "List scheduled work, optionally filtered by Job or status.",
                "arguments": ["job_id", "status"],
                "required": [],
                "returns": "A list of scheduled work items.",
                "stage": None,
            },
            {
                "name": "list_signals",
                "effect": "read",
                "summary": "List signals the store recorded — real changes worth attention.",
                "arguments": ["unread_only", "limit"],
                "required": [],
                "returns": "A list of Signals, newest first.",
                "stage": None,
            },
            {
                "name": "list_studies",
                "effect": "read",
                "summary": "List the studies opened for a Job.",
                "arguments": ["job_id"],
                "required": [],
                "returns": "A list of Studies. Empty until a study has been opened.",
                "stage": None,
            },
            {
                "name": "mark_signal_read",
                "effect": "write",
                "summary": "Mark a signal as read so it stops counting toward the unread badge.",
                "arguments": ["signal_id"],
                "required": ["signal_id"],
                "returns": "The updated Signal.",
                "stage": None,
            },
            {
                "name": "open_study",
                "effect": "write",
                "summary": "Open a named study pass over a Job at a given wave number.",
                "arguments": ["job_id", "name", "wave", "method_notes"],
                "required": ["job_id", "name", "wave"],
                "returns": "The created Study, opened as planned.",
                "stage": None,
            },
            {
                "name": "promote_evidence",
                "effect": "write",
                "summary": "Promote evidence to a Job or an Outcome.",
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
                "returns": "The created Job or Outcome.",
                "stage": None,
            },
            {
                "name": "propose_outcome",
                "effect": "write",
                "summary": "Propose a desired outcome mined from an evidence record.",
                "arguments": ["evidence_id"],
                "required": ["evidence_id"],
                "returns": "An OutcomeProposal ready for human approval.",
                "stage": "2",
            },
            {
                "name": "propose_strategy",
                "effect": "write",
                "summary": "Recommend the one innovation path the segments support.",
                "arguments": ["job_id"],
                "required": [],
                "returns": "The Strategy, including every path it beat and why.",
                "stage": "6",
            },
            {
                "name": "reject_proposal",
                "effect": "write",
                "summary": "Reject a proposal; nothing is written to the ODI store.",
                "arguments": ["proposal_id"],
                "required": ["proposal_id"],
                "returns": "The rejected OutcomeProposal.",
                "stage": "2",
            },
            {
                "name": "schedule_work",
                "effect": "write",
                "summary": "Schedule agent work with a cron or one-shot expression.",
                "arguments": [
                    "name",
                    "schedule_expression",
                    "agent_id",
                    "trigger_type",
                    "payload",
                    "job_id",
                ],
                "required": ["name", "schedule_expression"],
                "returns": "The created scheduled work item.",
                "stage": None,
            },
            {
                "name": "segment_market",
                "effect": "write",
                "summary": "Cluster the scored outcomes into outcome-based segments.",
                "arguments": ["job_id", "people"],
                "required": [],
                "returns": "The segments the outcomes clustered into, with verdict and confidence.",
                "stage": "5",
            },
            {
                "name": "trigger_scheduled_work",
                "effect": "write",
                "summary": "Dispatch a scheduled work item immediately.",
                "arguments": ["work_id"],
                "required": ["work_id"],
                "returns": "The dispatched scheduled work item.",
                "stage": None,
            },
            {
                "name": "unlink_outcome",
                "effect": "write",
                "summary": "Remove one V2MOM link from an Outcome.",
                "arguments": ["outcome_id", "field", "key"],
                "required": ["outcome_id", "field", "key"],
                "returns": "The updated Outcome.",
                "stage": "6",
            },
            {
                "name": "update_customer_outcome",
                "effect": "write",
                "summary": "Update a Customer Outcome's value metrics.",
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
                "returns": "The updated Customer Outcome.",
                "stage": None,
            },
            {
                "name": "update_job",
                "effect": "write",
                "summary": "Update a Job's name or description.",
                "arguments": ["job_id", "name", "description"],
                "required": ["job_id"],
                "returns": "The updated Job.",
                "stage": "1",
            },
            {
                "name": "update_outcome",
                "effect": "write",
                "summary": "Update an Outcome's statement or scores.",
                "arguments": ["outcome_id", "statement", "importance", "satisfaction", "step_id"],
                "required": ["outcome_id"],
                "returns": "The updated Outcome.",
                "stage": "2",
            },
            {
                "name": "update_step",
                "effect": "write",
                "summary": "Update a Step's name or order.",
                "arguments": ["step_id", "name", "order"],
                "required": ["step_id"],
                "returns": "The updated Step.",
                "stage": "3",
            },
        ]
    )


def _live_pin() -> Snapshot:
    return snapshot(
        {
            "add_customer_outcome": {
                "additionalProperties": False,
                "properties": {
                    "business_value": {"additionalProperties": True, "type": "object"},
                    "customer_value": {"additionalProperties": True, "type": "object"},
                    "job_id": {"type": "string"},
                    "step_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                },
                "required": ["job_id", "customer_value", "business_value"],
                "type": "object",
            },
            "add_evidence": {
                "additionalProperties": False,
                "properties": {
                    "content": {"type": "string"},
                    "item_type": {
                        "default": "manual",
                        "enum": ["catalog", "resource", "tool_result", "manual", "note"],
                        "type": "string",
                    },
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "name": {"type": "string"},
                    "origin": {
                        "default": "user",
                        "enum": ["user", "demo", "sample", "imported"],
                        "type": "string",
                    },
                    "outcome_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "raw": {
                        "anyOf": [
                            {"additionalProperties": True, "type": "object"},
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                    "source_kind": {"type": "string"},
                    "source_name": {"type": "string"},
                    "step_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "url": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                },
                "required": ["source_name", "source_kind", "name", "content"],
                "type": "object",
            },
            "add_job": {
                "additionalProperties": False,
                "properties": {
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "name": {"type": "string"},
                    "origin": {
                        "default": "user",
                        "enum": ["user", "demo", "sample", "imported"],
                        "type": "string",
                    },
                },
                "required": ["name"],
                "type": "object",
            },
            "add_outcome": {
                "additionalProperties": False,
                "properties": {
                    "claim_check": {
                        "anyOf": [
                            {"additionalProperties": True, "type": "object"},
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                    "importance": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "job_id": {"type": "string"},
                    "origin": {
                        "default": "user",
                        "enum": ["user", "demo", "sample", "imported"],
                        "type": "string",
                    },
                    "satisfaction": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "statement": {"type": "string"},
                    "step_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                },
                "required": ["job_id", "statement"],
                "type": "object",
            },
            "add_step": {
                "additionalProperties": False,
                "properties": {
                    "allow_empty_job_map": {"default": False, "type": "boolean"},
                    "job_id": {"type": "string"},
                    "name": {"type": "string"},
                    "order": {"type": "integer"},
                    "origin": {
                        "default": "user",
                        "enum": ["user", "demo", "sample", "imported"],
                        "type": "string",
                    },
                    "stage": {
                        "anyOf": [
                            {
                                "description": "Ulwick's Universal Job Map stages, in canonical order.",
                                "enum": [
                                    "define",
                                    "locate",
                                    "prepare",
                                    "confirm",
                                    "execute",
                                    "monitor",
                                    "modify",
                                    "conclude",
                                ],
                                "type": "string",
                            },
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                },
                "required": ["job_id", "name", "order"],
                "type": "object",
            },
            "approve_proposal": {
                "additionalProperties": False,
                "properties": {
                    "importance": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "proposal_id": {"type": "string"},
                    "satisfaction": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "statement": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                },
                "required": ["proposal_id"],
                "type": "object",
            },
            "cancel_scheduled_work": {
                "additionalProperties": False,
                "properties": {"work_id": {"type": "string"}},
                "required": ["work_id"],
                "type": "object",
            },
            "compute_opportunity": {
                "additionalProperties": False,
                "properties": {
                    "importance": {"type": "number"},
                    "satisfaction": {"type": "number"},
                },
                "required": ["importance", "satisfaction"],
                "type": "object",
            },
            "delete_customer_outcome": {
                "additionalProperties": False,
                "properties": {"outcome_id": {"type": "string"}},
                "required": ["outcome_id"],
                "type": "object",
            },
            "delete_evidence": {
                "additionalProperties": False,
                "properties": {"evidence_id": {"type": "string"}},
                "required": ["evidence_id"],
                "type": "object",
            },
            "delete_job": {
                "additionalProperties": False,
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
                "type": "object",
            },
            "delete_outcome": {
                "additionalProperties": False,
                "properties": {"outcome_id": {"type": "string"}},
                "required": ["outcome_id"],
                "type": "object",
            },
            "delete_step": {
                "additionalProperties": False,
                "properties": {"step_id": {"type": "string"}},
                "required": ["step_id"],
                "type": "object",
            },
            "dismiss_signal": {
                "additionalProperties": False,
                "properties": {"signal_id": {"type": "string"}},
                "required": ["signal_id"],
                "type": "object",
            },
            "evaluate_outcome": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "statement": {"type": "string"},
                },
                "required": ["statement"],
                "type": "object",
            },
            "get_capabilities": {"additionalProperties": False, "properties": {}, "type": "object"},
            "get_capabilities_manifest": {
                "additionalProperties": False,
                "properties": {},
                "type": "object",
            },
            "get_customer_outcome": {
                "additionalProperties": False,
                "properties": {"outcome_id": {"type": "string"}},
                "required": ["outcome_id"],
                "type": "object",
            },
            "get_evidence": {
                "additionalProperties": False,
                "properties": {"evidence_id": {"type": "string"}},
                "required": ["evidence_id"],
                "type": "object",
            },
            "get_health": {"additionalProperties": False, "properties": {}, "type": "object"},
            "get_job": {
                "additionalProperties": False,
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
                "type": "object",
            },
            "get_job_map": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"type": "string"},
                    "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "offset": {"default": 0, "type": "integer"},
                },
                "required": ["job_id"],
                "type": "object",
            },
            "get_jobs": {
                "additionalProperties": False,
                "properties": {
                    "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "offset": {"default": 0, "type": "integer"},
                },
                "type": "object",
            },
            "get_odi_framework_guidelines": {
                "additionalProperties": False,
                "properties": {},
                "type": "object",
            },
            "get_odi_schema": {"additionalProperties": False, "properties": {}, "type": "object"},
            "get_outcome": {
                "additionalProperties": False,
                "properties": {"outcome_id": {"type": "string"}},
                "required": ["outcome_id"],
                "type": "object",
            },
            "get_outcome_alignments": {
                "additionalProperties": False,
                "properties": {
                    "outcome_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}
                },
                "type": "object",
            },
            "get_outcomes": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"type": "string"},
                    "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "offset": {"default": 0, "type": "integer"},
                    "sort": {"default": "opportunity_score", "type": "string"},
                    "step_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                },
                "required": ["job_id"],
                "type": "object",
            },
            "get_scheduled_work": {
                "additionalProperties": False,
                "properties": {"work_id": {"type": "string"}},
                "required": ["work_id"],
                "type": "object",
            },
            "get_segments": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}
                },
                "type": "object",
            },
            "get_step": {
                "additionalProperties": False,
                "properties": {"step_id": {"type": "string"}},
                "required": ["step_id"],
                "type": "object",
            },
            "get_strategy": {"additionalProperties": False, "properties": {}, "type": "object"},
            "get_traceability_report": {
                "additionalProperties": False,
                "properties": {},
                "type": "object",
            },
            "link_outcome": {
                "additionalProperties": False,
                "properties": {
                    "field": {"type": "string"},
                    "outcome_id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["outcome_id", "field", "text"],
                "type": "object",
            },
            "list_customer_outcomes": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "offset": {"default": 0, "type": "integer"},
                },
                "type": "object",
            },
            "list_evidence": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "offset": {"default": 0, "type": "integer"},
                    "outcome_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "step_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                },
                "type": "object",
            },
            "list_proposals": {
                "additionalProperties": False,
                "properties": {
                    "status": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}
                },
                "type": "object",
            },
            "list_scheduled_work": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "status": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                },
                "type": "object",
            },
            "list_signals": {
                "additionalProperties": False,
                "properties": {
                    "limit": {"default": 50, "type": "integer"},
                    "unread_only": {"default": False, "type": "boolean"},
                },
                "type": "object",
            },
            "list_studies": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}
                },
                "type": "object",
            },
            "mark_signal_read": {
                "additionalProperties": False,
                "properties": {"signal_id": {"type": "string"}},
                "required": ["signal_id"],
                "type": "object",
            },
            "open_study": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"type": "string"},
                    "method_notes": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "name": {"type": "string"},
                    "wave": {"type": "integer"},
                },
                "required": ["job_id", "name", "wave"],
                "type": "object",
            },
            "promote_evidence": {
                "additionalProperties": False,
                "properties": {
                    "evidence_id": {"type": "string"},
                    "importance": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "name": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "satisfaction": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "statement": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "target": {"type": "string"},
                },
                "required": ["evidence_id", "target"],
                "type": "object",
            },
            "propose_outcome": {
                "additionalProperties": False,
                "properties": {"evidence_id": {"type": "string"}},
                "required": ["evidence_id"],
                "type": "object",
            },
            "propose_strategy": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}
                },
                "type": "object",
            },
            "reject_proposal": {
                "additionalProperties": False,
                "properties": {"proposal_id": {"type": "string"}},
                "required": ["proposal_id"],
                "type": "object",
            },
            "schedule_work": {
                "additionalProperties": False,
                "properties": {
                    "agent_id": {"default": "default-agent", "type": "string"},
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "name": {"type": "string"},
                    "payload": {
                        "anyOf": [
                            {"additionalProperties": True, "type": "object"},
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                    "schedule_expression": {"type": "string"},
                    "trigger_type": {"default": "oneshot", "type": "string"},
                },
                "required": ["name", "schedule_expression"],
                "type": "object",
            },
            "segment_market": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "people": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                },
                "type": "object",
            },
            "trigger_scheduled_work": {
                "additionalProperties": False,
                "properties": {"work_id": {"type": "string"}},
                "required": ["work_id"],
                "type": "object",
            },
            "unlink_outcome": {
                "additionalProperties": False,
                "properties": {
                    "field": {"type": "string"},
                    "key": {"type": "string"},
                    "outcome_id": {"type": "string"},
                },
                "required": ["outcome_id", "field", "key"],
                "type": "object",
            },
            "update_customer_outcome": {
                "additionalProperties": False,
                "properties": {
                    "business_statement": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "category": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "confidence": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "contextual_clarifier": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "detail": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "direction": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "estimated_annual_value": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "importance": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "object_of_control": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "outcome_id": {"type": "string"},
                    "satisfaction": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "statement": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "step_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "unit_of_measure": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "value_metrics": {
                        "anyOf": [
                            {
                                "items": {"additionalProperties": True, "type": "object"},
                                "type": "array",
                            },
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                },
                "required": ["outcome_id"],
                "type": "object",
            },
            "update_job": {
                "additionalProperties": False,
                "properties": {
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "job_id": {"type": "string"},
                    "name": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                },
                "required": ["job_id"],
                "type": "object",
            },
            "update_outcome": {
                "additionalProperties": False,
                "properties": {
                    "importance": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "outcome_id": {"type": "string"},
                    "satisfaction": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "statement": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "step_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                },
                "required": ["outcome_id"],
                "type": "object",
            },
            "update_step": {
                "additionalProperties": False,
                "properties": {
                    "name": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "order": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "step_id": {"type": "string"},
                },
                "required": ["step_id"],
                "type": "object",
            },
        }
    )


def _entity_pin() -> Snapshot:
    return snapshot(
        {
            "BusinessValue": {
                "$defs": {
                    "BusinessImpactCategory": {
                        "enum": [
                            "revenue_growth",
                            "cost_reduction",
                            "retention",
                            "risk_mitigation",
                            "operational_efficiency",
                            "compliance",
                            "brand_reputation",
                            "other",
                        ],
                        "title": "BusinessImpactCategory",
                        "type": "string",
                    }
                },
                "properties": {
                    "category": {"$ref": "#/$defs/BusinessImpactCategory"},
                    "confidence": {
                        "anyOf": [
                            {"maximum": 1.0, "minimum": 0.0, "type": "number"},
                            {"type": "null"},
                        ],
                        "default": None,
                        "title": "Confidence",
                    },
                    "detail": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "title": "Detail",
                    },
                    "estimated_annual_value": {
                        "anyOf": [{"minimum": 0.0, "type": "number"}, {"type": "null"}],
                        "default": None,
                        "title": "Estimated Annual Value",
                    },
                    "statement": {"title": "Statement", "type": "string"},
                },
                "required": ["category", "statement"],
                "title": "BusinessValue",
                "type": "object",
            },
            "CustomerOutcome": {
                "$defs": {
                    "BusinessImpactCategory": {
                        "enum": [
                            "revenue_growth",
                            "cost_reduction",
                            "retention",
                            "risk_mitigation",
                            "operational_efficiency",
                            "compliance",
                            "brand_reputation",
                            "other",
                        ],
                        "title": "BusinessImpactCategory",
                        "type": "string",
                    },
                    "BusinessValue": {
                        "properties": {
                            "category": {"$ref": "#/$defs/BusinessImpactCategory"},
                            "confidence": {
                                "anyOf": [
                                    {"maximum": 1.0, "minimum": 0.0, "type": "number"},
                                    {"type": "null"},
                                ],
                                "default": None,
                                "title": "Confidence",
                            },
                            "detail": {
                                "anyOf": [{"type": "string"}, {"type": "null"}],
                                "default": None,
                                "title": "Detail",
                            },
                            "estimated_annual_value": {
                                "anyOf": [{"minimum": 0.0, "type": "number"}, {"type": "null"}],
                                "default": None,
                                "title": "Estimated Annual Value",
                            },
                            "statement": {"title": "Statement", "type": "string"},
                        },
                        "required": ["category", "statement"],
                        "title": "BusinessValue",
                        "type": "object",
                    },
                    "CustomerValue": {
                        "properties": {
                            "contextual_clarifier": {
                                "anyOf": [{"type": "string"}, {"type": "null"}],
                                "default": None,
                                "title": "Contextual Clarifier",
                            },
                            "direction": {"$ref": "#/$defs/Direction"},
                            "importance": {
                                "maximum": 10.0,
                                "minimum": 1.0,
                                "title": "Importance",
                                "type": "number",
                            },
                            "object_of_control": {"title": "Object Of Control", "type": "string"},
                            "satisfaction": {
                                "maximum": 10.0,
                                "minimum": 1.0,
                                "title": "Satisfaction",
                                "type": "number",
                            },
                            "statement": {"title": "Statement", "type": "string"},
                            "unit_of_measure": {"title": "Unit Of Measure", "type": "string"},
                            "value_metrics": {
                                "items": {"$ref": "#/$defs/ValueMetric"},
                                "title": "Value Metrics",
                                "type": "array",
                            },
                        },
                        "required": [
                            "direction",
                            "unit_of_measure",
                            "object_of_control",
                            "statement",
                            "importance",
                            "satisfaction",
                        ],
                        "title": "CustomerValue",
                        "type": "object",
                    },
                    "Direction": {
                        "enum": ["minimize", "maximize"],
                        "title": "Direction",
                        "type": "string",
                    },
                    "ValueMetric": {
                        "properties": {
                            "direction": {"$ref": "#/$defs/Direction"},
                            "importance": {
                                "maximum": 10.0,
                                "minimum": 1.0,
                                "title": "Importance",
                                "type": "number",
                            },
                            "name": {"title": "Name", "type": "string"},
                            "satisfaction": {
                                "maximum": 10.0,
                                "minimum": 1.0,
                                "title": "Satisfaction",
                                "type": "number",
                            },
                            "unit_of_measure": {"title": "Unit Of Measure", "type": "string"},
                        },
                        "required": [
                            "name",
                            "direction",
                            "unit_of_measure",
                            "importance",
                            "satisfaction",
                        ],
                        "title": "ValueMetric",
                        "type": "object",
                    },
                },
                "properties": {
                    "business_value": {"$ref": "#/$defs/BusinessValue"},
                    "customer_value": {"$ref": "#/$defs/CustomerValue"},
                    "id": {"title": "Id", "type": "string"},
                    "job_id": {
                        "description": "The ID of the Job this outcome relates to",
                        "title": "Job Id",
                        "type": "string",
                    },
                    "quote_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "The Evidence record this outcome was promoted from",
                        "title": "Quote Id",
                    },
                    "step_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "The ID of the specific Step, if applicable",
                        "title": "Step Id",
                    },
                },
                "required": ["job_id", "customer_value", "business_value"],
                "title": "CustomerOutcome",
                "type": "object",
            },
            "CustomerValue": {
                "$defs": {
                    "Direction": {
                        "enum": ["minimize", "maximize"],
                        "title": "Direction",
                        "type": "string",
                    },
                    "ValueMetric": {
                        "properties": {
                            "direction": {"$ref": "#/$defs/Direction"},
                            "importance": {
                                "maximum": 10.0,
                                "minimum": 1.0,
                                "title": "Importance",
                                "type": "number",
                            },
                            "name": {"title": "Name", "type": "string"},
                            "satisfaction": {
                                "maximum": 10.0,
                                "minimum": 1.0,
                                "title": "Satisfaction",
                                "type": "number",
                            },
                            "unit_of_measure": {"title": "Unit Of Measure", "type": "string"},
                        },
                        "required": [
                            "name",
                            "direction",
                            "unit_of_measure",
                            "importance",
                            "satisfaction",
                        ],
                        "title": "ValueMetric",
                        "type": "object",
                    },
                },
                "properties": {
                    "contextual_clarifier": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "title": "Contextual Clarifier",
                    },
                    "direction": {"$ref": "#/$defs/Direction"},
                    "importance": {
                        "maximum": 10.0,
                        "minimum": 1.0,
                        "title": "Importance",
                        "type": "number",
                    },
                    "object_of_control": {"title": "Object Of Control", "type": "string"},
                    "satisfaction": {
                        "maximum": 10.0,
                        "minimum": 1.0,
                        "title": "Satisfaction",
                        "type": "number",
                    },
                    "statement": {"title": "Statement", "type": "string"},
                    "unit_of_measure": {"title": "Unit Of Measure", "type": "string"},
                    "value_metrics": {
                        "items": {"$ref": "#/$defs/ValueMetric"},
                        "title": "Value Metrics",
                        "type": "array",
                    },
                },
                "required": [
                    "direction",
                    "unit_of_measure",
                    "object_of_control",
                    "statement",
                    "importance",
                    "satisfaction",
                ],
                "title": "CustomerValue",
                "type": "object",
            },
            "Evidence": {
                "description": "A captured research record linked (optionally) to ODI artifacts.",
                "properties": {
                    "content": {
                        "description": "Normalized text content of the record",
                        "title": "Content",
                        "type": "string",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "item_type": {
                        "default": "manual",
                        "description": "Normalized record kind produced by the connector",
                        "enum": ["catalog", "resource", "tool_result", "manual", "note"],
                        "title": "Item Type",
                        "type": "string",
                    },
                    "job_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "Job this evidence supports",
                        "title": "Job Id",
                    },
                    "name": {
                        "description": "Short human-readable label for the record",
                        "title": "Name",
                        "type": "string",
                    },
                    "origin": {
                        "default": "user",
                        "description": "Provenance of the row: user, demo, sample, or imported",
                        "enum": ["user", "demo", "sample", "imported"],
                        "title": "Origin",
                        "type": "string",
                    },
                    "outcome_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "Desired Outcome this evidence supports",
                        "title": "Outcome Id",
                    },
                    "raw": {
                        "additionalProperties": True,
                        "description": "Original record payload",
                        "title": "Raw",
                        "type": "object",
                    },
                    "source_kind": {
                        "description": "Connector kind, e.g. mcp, rest, webhook, manual, interview. Provenance is `origin`, never this field.",
                        "title": "Source Kind",
                        "type": "string",
                    },
                    "source_name": {
                        "description": "Connector or person that produced the record",
                        "title": "Source Name",
                        "type": "string",
                    },
                    "step_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "Job-map Step this evidence supports",
                        "title": "Step Id",
                    },
                    "url": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "External URL/link to the signal/evidence in the source system",
                        "title": "Url",
                    },
                },
                "required": ["source_name", "source_kind", "name", "content"],
                "title": "Evidence",
                "type": "object",
            },
            "Job": {
                "properties": {
                    "description": {
                        "anyOf": [{"maxLength": 500, "type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "Detailed description of the Job",
                        "title": "Description",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "name": {
                        "description": "The name of the Job-to-be-Done",
                        "maxLength": 64,
                        "minLength": 3,
                        "pattern": "^[A-Za-z0-9 _-]+$",
                        "title": "Name",
                        "type": "string",
                    },
                    "origin": {
                        "default": "user",
                        "description": "Provenance of the row: user, demo, sample, or imported",
                        "enum": ["user", "demo", "sample", "imported"],
                        "title": "Origin",
                        "type": "string",
                    },
                },
                "required": ["name"],
                "title": "Job",
                "type": "object",
            },
            "Outcome": {
                "$defs": {
                    "ClaimCheck": {
                        "description": """\
The questions behind a score: what was asked, answered, or skipped.

Two numbers are not provenance. A score that carries a claim check says
which questions produced it — ``asked`` — and what came back: the
``answers`` the person gave and the ``skips`` with a recorded reason.

``verified`` is derived, never typed in: a check is verified when at least
one question was answered by the person. A check of only skips is
unverified, so an outcome built on an assumption says so instead of
borrowing the confidence of a number.\
""",
                        "properties": {
                            "answers": {
                                "description": "The answers the person gave, in order",
                                "items": {"type": "string"},
                                "title": "Answers",
                                "type": "array",
                            },
                            "asked": {
                                "description": "The questions put to the person",
                                "items": {"type": "string"},
                                "title": "Asked",
                                "type": "array",
                            },
                            "skips": {
                                "description": "Questions skipped, each with a reason",
                                "items": {"$ref": "#/$defs/ClaimSkip"},
                                "title": "Skips",
                                "type": "array",
                            },
                        },
                        "title": "ClaimCheck",
                        "type": "object",
                    },
                    "ClaimSkip": {
                        "description": """\
One question that went unanswered, and why it was skipped.

A skip without a reason is not a skip, it is a missing answer, so
``reason`` is required and must not be blank.\
""",
                        "properties": {
                            "question": {
                                "description": "The question that was not answered",
                                "title": "Question",
                                "type": "string",
                            },
                            "reason": {
                                "description": "Why it was skipped; never blank",
                                "title": "Reason",
                                "type": "string",
                            },
                        },
                        "required": ["question", "reason"],
                        "title": "ClaimSkip",
                        "type": "object",
                    },
                    "OutcomeAlignment": {
                        "description": """\
A claim that an Outcome advances one V2MOM objective.

``field`` is ``method`` or ``measure``; ``key`` is the content key computed
from ``field`` and ``text`` when the link was made; ``text`` is the
canonical objective text then. Storing the key *and* the text means a
reworded objective shows up as drift carrying the text the outcome was
linked to, and the key is never re-derived under a later normalization rule.\
""",
                        "properties": {
                            "field": {
                                "description": "Which V2MOM list the objective lives in",
                                "enum": ["method", "measure"],
                                "title": "Field",
                                "type": "string",
                            },
                            "key": {
                                "description": "Frozen content key for the objective text",
                                "title": "Key",
                                "type": "string",
                            },
                            "text": {
                                "description": "The objective text as it read when the link was made",
                                "title": "Text",
                                "type": "string",
                            },
                        },
                        "required": ["field", "key", "text"],
                        "title": "OutcomeAlignment",
                        "type": "object",
                    },
                },
                "properties": {
                    "claim_check": {
                        "anyOf": [{"$ref": "#/$defs/ClaimCheck"}, {"type": "null"}],
                        "default": None,
                        "description": "The questions that produced the score, and what came back",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "importance": {
                        "anyOf": [
                            {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                            {"type": "null"},
                        ],
                        "default": None,
                        "description": "Importance score (1-10)",
                        "title": "Importance",
                    },
                    "job_id": {
                        "description": "The ID of the Job this outcome relates to",
                        "title": "Job Id",
                        "type": "string",
                    },
                    "opportunity_score": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                        "description": "Opportunity score (Importance + max(Importance - Satisfaction, 0))",
                        "title": "Opportunity Score",
                    },
                    "origin": {
                        "default": "user",
                        "description": "Provenance of the row: user, demo, sample, or imported",
                        "enum": ["user", "demo", "sample", "imported"],
                        "title": "Origin",
                        "type": "string",
                    },
                    "satisfaction": {
                        "anyOf": [
                            {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                            {"type": "null"},
                        ],
                        "default": None,
                        "description": "Current satisfaction score (1-10)",
                        "title": "Satisfaction",
                    },
                    "statement": {
                        "description": "The desired outcome statement (e.g., 'Minimize the time it takes to...')",
                        "title": "Statement",
                        "type": "string",
                    },
                    "step_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "The ID of the specific Step, if applicable",
                        "title": "Step Id",
                    },
                    "study_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "The Study wave this outcome was measured in, or None for a row that predates studies",
                        "title": "Study Id",
                    },
                    "trace": {
                        "description": "The V2MOM methods and measures this outcome advances. Empty means the outcome is unlinked, which the traceability report calls an orphan.",
                        "items": {"$ref": "#/$defs/OutcomeAlignment"},
                        "title": "Trace",
                        "type": "array",
                    },
                },
                "required": ["job_id", "statement"],
                "title": "Outcome",
                "type": "object",
            },
            "OutcomeAlignment": {
                "description": """\
A claim that an Outcome advances one V2MOM objective.

``field`` is ``method`` or ``measure``; ``key`` is the content key computed
from ``field`` and ``text`` when the link was made; ``text`` is the
canonical objective text then. Storing the key *and* the text means a
reworded objective shows up as drift carrying the text the outcome was
linked to, and the key is never re-derived under a later normalization rule.\
""",
                "properties": {
                    "field": {
                        "description": "Which V2MOM list the objective lives in",
                        "enum": ["method", "measure"],
                        "title": "Field",
                        "type": "string",
                    },
                    "key": {
                        "description": "Frozen content key for the objective text",
                        "title": "Key",
                        "type": "string",
                    },
                    "text": {
                        "description": "The objective text as it read when the link was made",
                        "title": "Text",
                        "type": "string",
                    },
                },
                "required": ["field", "key", "text"],
                "title": "OutcomeAlignment",
                "type": "object",
            },
            "ScheduledWork": {
                "$defs": {
                    "ScheduledWorkStatus": {
                        "enum": [
                            "pending",
                            "scheduled",
                            "running",
                            "completed",
                            "failed",
                            "cancelled",
                        ],
                        "title": "ScheduledWorkStatus",
                        "type": "string",
                    },
                    "ScheduledWorkTriggerType": {
                        "enum": ["oneshot", "cron", "interval"],
                        "title": "ScheduledWorkTriggerType",
                        "type": "string",
                    },
                },
                "description": "A scheduled task or agent run in the cloud.",
                "properties": {
                    "agent_id": {
                        "default": "default-agent",
                        "description": "ID/alias of the agent assigned to run the work",
                        "title": "Agent Id",
                        "type": "string",
                    },
                    "created_at": {"title": "Created At", "type": "string"},
                    "id": {"title": "Id", "type": "string"},
                    "job_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "Associated ODI Job ID, if any",
                        "title": "Job Id",
                    },
                    "last_run_at": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "ISO timestamp of last execution",
                        "title": "Last Run At",
                    },
                    "name": {
                        "description": "Name or title of the scheduled work task",
                        "title": "Name",
                        "type": "string",
                    },
                    "next_run_at": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "ISO timestamp of next scheduled execution",
                        "title": "Next Run At",
                    },
                    "payload": {
                        "additionalProperties": True,
                        "description": "Parameters or prompt for the cloud task",
                        "title": "Payload",
                        "type": "object",
                    },
                    "result_summary": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "Execution outcome or error summary",
                        "title": "Result Summary",
                    },
                    "schedule_expression": {
                        "description": "ISO timestamp, relative delay, or cron expression (e.g. '0 * * * *' or '+1h')",
                        "title": "Schedule Expression",
                        "type": "string",
                    },
                    "status": {
                        "$ref": "#/$defs/ScheduledWorkStatus",
                        "default": "scheduled",
                        "description": "Current status of the task",
                    },
                    "trigger_type": {
                        "$ref": "#/$defs/ScheduledWorkTriggerType",
                        "default": "oneshot",
                        "description": "Trigger mechanism (oneshot, cron, interval)",
                    },
                },
                "required": ["name", "schedule_expression"],
                "title": "ScheduledWork",
                "type": "object",
            },
            "Segment": {
                "$defs": {
                    "SegmentVerdict": {
                        "description": "Stage 5's verdict on a group of people, computed from their outcomes.",
                        "enum": ["underserved", "overserved", "appropriately_served"],
                        "title": "SegmentVerdict",
                        "type": "string",
                    }
                },
                "description": """\
A group of people plus the functional job they are trying to do.

The unit of analysis is the outcome: ``outcome_ids`` is the evidence, and
``verdict`` is derived from it, never typed in. ``verdict`` is ``None`` when
an outcome in the group has no score, because a segment cannot be classified
from partial evidence. No demographic attribute appears here by design.\
""",
                "properties": {
                    "confidence": {
                        "description": "How much evidence supports this",
                        "maximum": 1.0,
                        "minimum": 0.0,
                        "title": "Confidence",
                        "type": "number",
                    },
                    "created_at": {"format": "date-time", "title": "Created At", "type": "string"},
                    "id": {"title": "Id", "type": "string"},
                    "job_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "The Job this segment is scoped to",
                        "title": "Job Id",
                    },
                    "job_statement": {
                        "description": "The functional job in their words",
                        "title": "Job Statement",
                        "type": "string",
                    },
                    "name": {
                        "description": 'Human label, e.g. "Platform engineers, secrets rotation"',
                        "title": "Name",
                        "type": "string",
                    },
                    "outcome_ids": {
                        "description": "The evidence for this segment",
                        "items": {"type": "string"},
                        "title": "Outcome Ids",
                        "type": "array",
                    },
                    "people": {
                        "description": "The group, in the person's words when they are recorded",
                        "title": "People",
                        "type": "string",
                    },
                    "people_inferred": {
                        "default": False,
                        "description": "True when `people` was derived from the outcomes, not supplied",
                        "title": "People Inferred",
                        "type": "boolean",
                    },
                    "rationale": {
                        "description": "Why this verdict, naming the outcomes behind it",
                        "title": "Rationale",
                        "type": "string",
                    },
                    "verdict": {
                        "anyOf": [{"$ref": "#/$defs/SegmentVerdict"}, {"type": "null"}],
                        "default": None,
                        "description": "Derived from the outcomes; None means not enough signal",
                    },
                },
                "required": ["name", "people", "job_statement", "rationale", "confidence"],
                "title": "Segment",
                "type": "object",
            },
            "Signal": {
                "$defs": {
                    "SignalKind": {
                        "description": "The facts a signal may report. Every kind here has a real producer.",
                        "enum": [
                            "outcome_scored",
                            "opportunity_crossed",
                            "evidence_ingested",
                            "evidence_promoted",
                            "job_added",
                            "job_map_completed",
                            "segment_identified",
                            "strategy_proposed",
                        ],
                        "title": "SignalKind",
                        "type": "string",
                    }
                },
                "description": "One fact that happened in the store, surfaced in the Catch Up feed.",
                "properties": {
                    "created_at": {"format": "date-time", "title": "Created At", "type": "string"},
                    "detail": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "title": "Detail",
                    },
                    "dismissed_at": {
                        "anyOf": [{"format": "date-time", "type": "string"}, {"type": "null"}],
                        "default": None,
                        "title": "Dismissed At",
                    },
                    "fingerprint": {
                        "description": "sha256 of kind|subject_kind|subject_id|discriminator, plus source event id",
                        "title": "Fingerprint",
                        "type": "string",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "kind": {"$ref": "#/$defs/SignalKind"},
                    "read_at": {
                        "anyOf": [{"format": "date-time", "type": "string"}, {"type": "null"}],
                        "default": None,
                        "title": "Read At",
                    },
                    "severity": {
                        "default": "info",
                        "enum": ["info", "notice", "urgent"],
                        "title": "Severity",
                        "type": "string",
                    },
                    "subject_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "title": "Subject Id",
                    },
                    "subject_kind": {
                        "anyOf": [
                            {
                                "enum": [
                                    "job",
                                    "step",
                                    "outcome",
                                    "evidence",
                                    "connector",
                                    "agent_work",
                                    "segment",
                                    "strategy",
                                ],
                                "type": "string",
                            },
                            {"type": "null"},
                        ],
                        "default": None,
                        "title": "Subject Kind",
                    },
                    "suppressed": {"default": False, "title": "Suppressed", "type": "boolean"},
                    "title": {
                        "description": "One line, at most 120 characters",
                        "maxLength": 120,
                        "title": "Title",
                        "type": "string",
                    },
                },
                "required": ["kind", "title", "fingerprint"],
                "title": "Signal",
                "type": "object",
            },
            "Step": {
                "$defs": {
                    "JobStage": {
                        "description": "Ulwick's Universal Job Map stages, in canonical order.",
                        "enum": [
                            "define",
                            "locate",
                            "prepare",
                            "confirm",
                            "execute",
                            "monitor",
                            "modify",
                            "conclude",
                        ],
                        "title": "JobStage",
                        "type": "string",
                    }
                },
                "properties": {
                    "id": {"title": "Id", "type": "string"},
                    "job_id": {
                        "description": "The ID of the Job this step belongs to",
                        "title": "Job Id",
                        "type": "string",
                    },
                    "name": {
                        "description": "The name of the job step",
                        "title": "Name",
                        "type": "string",
                    },
                    "order": {
                        "description": "The chronological order of this step in the job map",
                        "title": "Order",
                        "type": "integer",
                    },
                    "origin": {
                        "default": "user",
                        "description": "Provenance of the row: user, demo, sample, or imported",
                        "enum": ["user", "demo", "sample", "imported"],
                        "title": "Origin",
                        "type": "string",
                    },
                    "stage": {
                        "anyOf": [{"$ref": "#/$defs/JobStage"}, {"type": "null"}],
                        "default": None,
                        "description": "The Universal Job Map stage this step belongs to",
                    },
                    "stage_index": {
                        "anyOf": [
                            {"maximum": 8, "minimum": 1, "type": "integer"},
                            {"type": "null"},
                        ],
                        "default": None,
                        "description": "Position (1-8) in the canonical stage order",
                        "title": "Stage Index",
                    },
                },
                "required": ["job_id", "name", "order"],
                "title": "Step",
                "type": "object",
            },
            "Strategy": {
                "$defs": {
                    "StrategyKind": {
                        "description": "Stage 6's three strategic paths.",
                        "enum": ["differentiated", "disruptive", "new_market"],
                        "title": "StrategyKind",
                        "type": "string",
                    }
                },
                "description": """\
One recommended innovation path, with the paths it beat recorded.

A strategy without its rejections is a conclusion, not a recommendation, so
``rejected`` carries one entry for every kind that was not chosen.\
""",
                "properties": {
                    "bets": {
                        "description": "The proposed moves",
                        "items": {"type": "string"},
                        "title": "Bets",
                        "type": "array",
                    },
                    "created_at": {"format": "date-time", "title": "Created At", "type": "string"},
                    "id": {"title": "Id", "type": "string"},
                    "kind": {"$ref": "#/$defs/StrategyKind"},
                    "rejected": {
                        "description": '[{"kind": "disruptive", "why": "..."}]',
                        "items": {"additionalProperties": True, "type": "object"},
                        "title": "Rejected",
                        "type": "array",
                    },
                    "segment_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "The segment this bet is aimed at",
                        "title": "Segment Id",
                    },
                    "thesis": {
                        "description": "One paragraph: why this path, from the evidence",
                        "title": "Thesis",
                        "type": "string",
                    },
                },
                "required": ["kind", "thesis"],
                "title": "Strategy",
                "type": "object",
            },
            "Study": {
                "$defs": {
                    "StudyStatus": {
                        "description": "Where a study is in its own life: opened, collecting, or closed.",
                        "enum": ["planned", "fielding", "closed"],
                        "title": "StudyStatus",
                        "type": "string",
                    }
                },
                "description": """\
One named pass over a Job, and the wave number of that pass.

A study is a container, not a measurement: it names a slice of research so a
later wave can be compared with an earlier one. ``wave`` is unique per
``(job_id, name)`` within the store — that guarantee needs to see the other
rows, so it lives in the service, while the model owns the invariants it can
check alone: a wave is a positive pass number, and ``closed_at`` appears if
and only if the study is closed.\
""",
                "properties": {
                    "closed_at": {
                        "anyOf": [{"format": "date-time", "type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "Set once, when the study closes",
                        "title": "Closed At",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "job_id": {
                        "description": "The Job this study takes one pass over",
                        "title": "Job Id",
                        "type": "string",
                    },
                    "method_notes": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "How this pass was run, so a later wave is comparable",
                        "title": "Method Notes",
                    },
                    "name": {
                        "description": "Human label for the study, e.g. 'reconciliation sweep'",
                        "title": "Name",
                        "type": "string",
                    },
                    "opened_at": {"format": "date-time", "title": "Opened At", "type": "string"},
                    "status": {
                        "$ref": "#/$defs/StudyStatus",
                        "default": "planned",
                        "description": "Where the study is in its life",
                    },
                    "wave": {
                        "description": "1-based pass number within (job_id, name)",
                        "minimum": 1,
                        "title": "Wave",
                        "type": "integer",
                    },
                },
                "required": ["job_id", "name", "wave"],
                "title": "Study",
                "type": "object",
            },
            "V2MOM": {
                "description": """\
The domain's V2MOM artifact: Vision, Values, Methods, Obstacles, Measures.

Only ``vision`` has an input path today, in the Studio's context
conversation. Nothing extracts the other four from a conversation and no
surface captures them, so a V2MOM in practice is its vision and four empty
lists.\
""",
                "properties": {
                    "measures": {
                        "description": "Metrics and key results that measure success",
                        "items": {"type": "string"},
                        "title": "Measures",
                        "type": "array",
                    },
                    "methods": {
                        "description": "Actions and strategies to achieve the vision",
                        "items": {"type": "string"},
                        "title": "Methods",
                        "type": "array",
                    },
                    "obstacles": {
                        "description": "Challenges and risks that stand in the way",
                        "items": {"type": "string"},
                        "title": "Obstacles",
                        "type": "array",
                    },
                    "values": {
                        "description": "Principles and beliefs that guide decisions",
                        "items": {"type": "string"},
                        "title": "Values",
                        "type": "array",
                    },
                    "vision": {
                        "default": "",
                        "description": "What you want to achieve or create",
                        "title": "Vision",
                        "type": "string",
                    },
                },
                "title": "V2MOM",
                "type": "object",
            },
            "ValueMetric": {
                "$defs": {
                    "Direction": {
                        "enum": ["minimize", "maximize"],
                        "title": "Direction",
                        "type": "string",
                    }
                },
                "properties": {
                    "direction": {"$ref": "#/$defs/Direction"},
                    "importance": {
                        "maximum": 10.0,
                        "minimum": 1.0,
                        "title": "Importance",
                        "type": "number",
                    },
                    "name": {"title": "Name", "type": "string"},
                    "satisfaction": {
                        "maximum": 10.0,
                        "minimum": 1.0,
                        "title": "Satisfaction",
                        "type": "number",
                    },
                    "unit_of_measure": {"title": "Unit Of Measure", "type": "string"},
                },
                "required": ["name", "direction", "unit_of_measure", "importance", "satisfaction"],
                "title": "ValueMetric",
                "type": "object",
            },
        }
    )


async def _live_schemas() -> dict[str, dict[str, Any]]:
    """Every input schema the in-memory server serves, as one mapping."""
    async with Client(mcp) as client:
        tools: Sequence[Any] = await client.list_tools()
    return {tool.name: tool.input_schema for tool in tools}


def test_declared_tool_contract_is_pinned() -> None:
    _assert_pinned(DECLARED, _tool_spec_rows(), _declared_pin())


@pytest.mark.asyncio
async def test_live_registry_input_schemas_are_pinned() -> None:
    _assert_pinned(LIVE, _live_rows(await _live_schemas()), _live_pin())


def test_published_entity_schema_is_pinned() -> None:
    _assert_pinned(ENTITIES, _entity_rows(odi_schema()), _entity_pin())


def test_generation_does_not_depend_on_iteration_order() -> None:
    """A pin that churns with dict order is a pin nobody reads."""
    assert _tool_spec_rows(dict(reversed(list(TOOL_SPECS.items())))) == _tool_spec_rows()

    schema = odi_schema()
    reversed_schema = {
        name: dict(reversed(list(entity.items())))
        for name, entity in reversed(list(schema.items()))
    }
    assert _entity_rows(reversed_schema) == _entity_rows(schema)

    rows = _live_rows({"b": {"z": 1, "a": [2, {"y": 3, "x": 4}]}, "a": {"type": "object"}})
    assert rows == _live_rows({"a": {"type": "object"}, "b": {"a": [2, {"x": 4, "y": 3}], "z": 1}})
    assert list(rows["b"]) == ["a", "z"]


def test_renaming_a_declared_argument_fails_the_pin(monkeypatch) -> None:
    """The drift class this gate exists for: an agent's call stops matching."""
    renamed = replace(TOOL_SPECS["add_job"], arguments=("name", "descrption", "origin"))
    monkeypatch.setitem(TOOL_SPECS, "add_job", renamed)
    pinned = get_snapshot_value(_declared_pin())

    with pytest.raises(AssertionError) as drift:
        _assert_pinned(DECLARED, _tool_spec_rows(), pinned)

    assert "add_job" in str(drift.value)
    assert "descrption" in str(drift.value)


def test_making_a_required_argument_optional_fails_the_pin(monkeypatch) -> None:
    """Dropping `name` from the required list must not look like the same contract."""
    silent = replace(TOOL_SPECS["add_job"], required=())
    monkeypatch.setitem(TOOL_SPECS, "add_job", silent)
    pinned = get_snapshot_value(_declared_pin())

    with pytest.raises(AssertionError) as drift:
        _assert_pinned(DECLARED, _tool_spec_rows(), pinned)

    assert "add_job.required" in str(drift.value)


def test_retyping_a_live_argument_fails_the_pin() -> None:
    """A `string` that becomes an `integer` is a breaking change, not a typo."""
    pinned = get_snapshot_value(_live_pin())
    schemas = copy.deepcopy(pinned)
    schemas["add_job"]["properties"]["name"]["type"] = "integer"

    with pytest.raises(AssertionError) as drift:
        _assert_pinned(LIVE, _live_rows(schemas), pinned)

    assert "add_job.properties.name.type" in str(drift.value)


def test_a_live_tool_that_disappears_fails_the_pin() -> None:
    pinned = get_snapshot_value(_live_pin())
    schemas = copy.deepcopy(pinned)
    del schemas["get_job"]

    with pytest.raises(AssertionError) as drift:
        _assert_pinned(LIVE, _live_rows(schemas), pinned)

    assert "get_job: gone" in str(drift.value)


def test_an_unexpected_live_tool_fails_the_pin() -> None:
    pinned = get_snapshot_value(_live_pin())
    schemas = copy.deepcopy(pinned)
    schemas["drop_everything"] = {"properties": {}, "type": "object"}

    with pytest.raises(AssertionError) as drift:
        _assert_pinned(LIVE, _live_rows(schemas), pinned)

    assert "drop_everything: new" in str(drift.value)


def test_dropping_a_field_from_an_entity_schema_fails_the_pin() -> None:
    pinned = get_snapshot_value(_entity_pin())
    schema = copy.deepcopy(pinned)
    del schema["Job"]["properties"]["origin"]

    with pytest.raises(AssertionError) as drift:
        _assert_pinned(ENTITIES, _entity_rows(schema), pinned)

    assert "Job.properties.origin: gone" in str(drift.value)


def test_a_renamed_entity_field_is_reported_as_gone_and_new() -> None:
    pinned = get_snapshot_value(_entity_pin())
    schema = copy.deepcopy(pinned)
    schema["Outcome"]["properties"]["origin_x"] = schema["Outcome"]["properties"].pop("origin")

    with pytest.raises(AssertionError) as drift:
        _assert_pinned(ENTITIES, _entity_rows(schema), pinned)

    message = str(drift.value)
    assert "Outcome.properties.origin: gone" in message
    assert "Outcome.properties.origin_x: new" in message
