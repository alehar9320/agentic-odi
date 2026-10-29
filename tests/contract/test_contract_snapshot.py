"""ALH-61 / H1 — pin the contract, fail on drift.

Run ``uv run pytest tests/contract/test_contract_snapshot.py --inline-snapshot=fix``
to regenerate the snapshots below. Review the diff like code before committing;
CI never accepts a snapshot automatically, so drift fails the build.

Three surfaces are pinned together, because snapshotting only the declared
contract would miss drift between the declaration and the live server:

1. ``contract.TOOL_SPECS`` — the declared tool surface.
2. The live FastMCP registry's per-tool ``input_schema`` — what an agent sees,
   including argument types and defaults.
3. ``schema.odi_schema()`` — the entity schemas.

Ordering is normalized (every mapping and list sorted) so repeated generation
is stable regardless of registry or dictionary iteration order. Semantic
defaults, required fields and types are preserved exactly.
"""

from __future__ import annotations

from typing import Any

import pytest
from agentic_odi_core.contract import TOOL_SPECS
from agentic_odi_core.schema import odi_schema
from agentic_odi_mcp_server.mcp_server import mcp
from fastmcp import Client
from inline_snapshot import snapshot


def _normalize(value: Any) -> Any:
    """Sort every mapping and list so generation is iteration-order independent."""
    if isinstance(value, dict):
        return {key: _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return sorted((_normalize(item) for item in value), key=repr)
    return value


def declared_tool_surface() -> dict[str, Any]:
    return _normalize(
        {
            name: {
                "summary": spec.summary,
                "effect": spec.effect.value,
                "arguments": list(spec.arguments),
                "required": list(spec.required),
                "returns": spec.returns,
                "stage": spec.stage,
            }
            for name, spec in TOOL_SPECS.items()
        }
    )


async def live_tool_surface() -> dict[str, Any]:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    return _normalize({tool.name: tool.input_schema for tool in tools})


@pytest.mark.asyncio
async def test_live_registry_snapshot() -> None:
    assert await live_tool_surface() == snapshot(
        {
            "add_customer_outcome": {
                "additionalProperties": False,
                "properties": {
                    "business_value": {"additionalProperties": True, "type": "object"},
                    "customer_value": {"additionalProperties": True, "type": "object"},
                    "job_id": {"type": "string"},
                    "step_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
                "required": ["business_value", "customer_value", "job_id"],
                "type": "object",
            },
            "add_evidence": {
                "additionalProperties": False,
                "properties": {
                    "content": {"type": "string"},
                    "item_type": {
                        "default": "manual",
                        "enum": ["catalog", "manual", "note", "resource", "tool_result"],
                        "type": "string",
                    },
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "name": {"type": "string"},
                    "outcome_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
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
                    "step_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
                "required": ["content", "name", "source_kind", "source_name"],
                "type": "object",
            },
            "add_job": {
                "additionalProperties": False,
                "properties": {
                    "description": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "name": {"type": "string"},
                },
                "required": ["name"],
                "type": "object",
            },
            "add_outcome": {
                "additionalProperties": False,
                "properties": {
                    "importance": {"type": "number"},
                    "job_id": {"type": "string"},
                    "satisfaction": {"type": "number"},
                    "statement": {"type": "string"},
                    "step_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
                "required": ["importance", "job_id", "satisfaction", "statement"],
                "type": "object",
            },
            "add_step": {
                "additionalProperties": False,
                "properties": {
                    "allow_empty_job_map": {"default": False, "type": "boolean"},
                    "job_id": {"type": "string"},
                    "name": {"type": "string"},
                    "order": {"type": "integer"},
                    "stage": {
                        "anyOf": [
                            {
                                "description": "Ulwick's Universal Job Map stages, in canonical order.",
                                "enum": [
                                    "conclude",
                                    "confirm",
                                    "define",
                                    "execute",
                                    "locate",
                                    "modify",
                                    "monitor",
                                    "prepare",
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
            "evaluate_outcome": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
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
            "get_outcomes": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"type": "string"},
                    "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "offset": {"default": 0, "type": "integer"},
                    "sort": {"default": "opportunity_score", "type": "string"},
                    "step_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
                "required": ["job_id"],
                "type": "object",
            },
            "get_step": {
                "additionalProperties": False,
                "properties": {"step_id": {"type": "string"}},
                "required": ["step_id"],
                "type": "object",
            },
            "list_customer_outcomes": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "offset": {"default": 0, "type": "integer"},
                },
                "type": "object",
            },
            "list_evidence": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "offset": {"default": 0, "type": "integer"},
                    "outcome_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "step_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
                "type": "object",
            },
            "promote_evidence": {
                "additionalProperties": False,
                "properties": {
                    "evidence_id": {"type": "string"},
                    "importance": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                    },
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "name": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "satisfaction": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                    },
                    "statement": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "target": {"type": "string"},
                },
                "required": ["evidence_id", "target"],
                "type": "object",
            },
            "update_customer_outcome": {
                "additionalProperties": False,
                "properties": {
                    "business_statement": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "category": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "confidence": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                    },
                    "contextual_clarifier": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "detail": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "direction": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "estimated_annual_value": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                    },
                    "importance": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                    },
                    "object_of_control": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "outcome_id": {"type": "string"},
                    "satisfaction": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                    },
                    "statement": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "step_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "unit_of_measure": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
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
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "job_id": {"type": "string"},
                    "name": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
                "required": ["job_id"],
                "type": "object",
            },
            "update_outcome": {
                "additionalProperties": False,
                "properties": {
                    "importance": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                    },
                    "outcome_id": {"type": "string"},
                    "satisfaction": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                    },
                    "statement": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "step_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
                "required": ["outcome_id"],
                "type": "object",
            },
            "update_step": {
                "additionalProperties": False,
                "properties": {
                    "name": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "order": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "step_id": {"type": "string"},
                },
                "required": ["step_id"],
                "type": "object",
            },
        }
    )


@pytest.mark.asyncio
async def test_live_registry_agrees_with_the_declared_contract() -> None:
    """The declaration and the server must not disagree, independent of the snapshot."""
    live = await live_tool_surface()

    assert set(live) == set(TOOL_SPECS)
    for name, spec in TOOL_SPECS.items():
        schema = live[name]
        assert set(schema.get("properties", {})) == set(spec.arguments), name
        assert set(schema.get("required", [])) == set(spec.required), name


def test_declared_tool_surface_snapshot() -> None:
    assert declared_tool_surface() == snapshot(
        {
            "add_customer_outcome": {
                "arguments": ["business_value", "customer_value", "job_id", "step_id"],
                "effect": "write",
                "required": ["business_value", "customer_value", "job_id"],
                "returns": "The created Customer Outcome.",
                "stage": None,
                "summary": "Add a Customer Outcome pairing customer and business value.",
            },
            "add_evidence": {
                "arguments": [
                    "content",
                    "item_type",
                    "job_id",
                    "name",
                    "outcome_id",
                    "raw",
                    "source_kind",
                    "source_name",
                    "step_id",
                ],
                "effect": "write",
                "required": ["content", "name", "source_kind", "source_name"],
                "returns": "The created Evidence record.",
                "stage": None,
                "summary": "Capture an evidence record from a connector.",
            },
            "add_job": {
                "arguments": ["description", "name"],
                "effect": "write",
                "required": ["name"],
                "returns": "The created Job.",
                "stage": "1",
                "summary": "Create a new Job-to-be-Done.",
            },
            "add_outcome": {
                "arguments": ["importance", "job_id", "satisfaction", "statement", "step_id"],
                "effect": "write",
                "required": ["importance", "job_id", "satisfaction", "statement"],
                "returns": "The created Outcome.",
                "stage": "2",
                "summary": "Add a desired Outcome to a Job.",
            },
            "add_step": {
                "arguments": ["allow_empty_job_map", "job_id", "name", "order", "stage"],
                "effect": "write",
                "required": ["job_id", "name", "order"],
                "returns": "The created Step.",
                "stage": "3",
                "summary": "Add a step to a Job's job map.",
            },
            "compute_opportunity": {
                "arguments": ["importance", "satisfaction"],
                "effect": "write",
                "required": ["importance", "satisfaction"],
                "returns": "The opportunity score as a float.",
                "stage": "4",
                "summary": "Compute an ODI opportunity score from importance and satisfaction.",
            },
            "delete_customer_outcome": {
                "arguments": ["outcome_id"],
                "effect": "destructive",
                "required": ["outcome_id"],
                "returns": "The deleted Customer Outcome ID.",
                "stage": None,
                "summary": "Delete a Customer Outcome.",
            },
            "delete_evidence": {
                "arguments": ["evidence_id"],
                "effect": "destructive",
                "required": ["evidence_id"],
                "returns": "The deleted Evidence ID.",
                "stage": None,
                "summary": "Delete an evidence record.",
            },
            "delete_job": {
                "arguments": ["job_id"],
                "effect": "destructive",
                "required": ["job_id"],
                "returns": "The deleted Job ID.",
                "stage": "1",
                "summary": "Delete a Job and its cascading dependents.",
            },
            "delete_outcome": {
                "arguments": ["outcome_id"],
                "effect": "destructive",
                "required": ["outcome_id"],
                "returns": "The deleted Outcome ID.",
                "stage": "2",
                "summary": "Delete a desired Outcome.",
            },
            "delete_step": {
                "arguments": ["step_id"],
                "effect": "destructive",
                "required": ["step_id"],
                "returns": "The deleted Step ID.",
                "stage": "3",
                "summary": "Delete a Step and its cascading dependents.",
            },
            "evaluate_outcome": {
                "arguments": ["job_id", "statement"],
                "effect": "write",
                "required": ["statement"],
                "returns": "A verdict with coded issues and suggestions.",
                "stage": "2",
                "summary": "Evaluate an outcome statement against ODI format rules.",
            },
            "get_capabilities": {
                "arguments": [],
                "effect": "read",
                "required": [],
                "returns": "A grouped summary of every tool.",
                "stage": None,
                "summary": "Get a human-readable list of all available tools.",
            },
            "get_capabilities_manifest": {
                "arguments": [],
                "effect": "read",
                "required": [],
                "returns": "The full tool manifest JSON.",
                "stage": None,
                "summary": "Get a machine-readable manifest of all tools.",
            },
            "get_customer_outcome": {
                "arguments": ["outcome_id"],
                "effect": "read",
                "required": ["outcome_id"],
                "returns": "The Customer Outcome, or an error string if not found.",
                "stage": None,
                "summary": "Get a single Customer Outcome by ID.",
            },
            "get_evidence": {
                "arguments": ["evidence_id"],
                "effect": "read",
                "required": ["evidence_id"],
                "returns": "The Evidence record, or an error string if not found.",
                "stage": None,
                "summary": "Get a single evidence record by ID.",
            },
            "get_job": {
                "arguments": ["job_id"],
                "effect": "read",
                "required": ["job_id"],
                "returns": "The Job, or an error string if not found.",
                "stage": "1",
                "summary": "Get a single Job by ID.",
            },
            "get_job_map": {
                "arguments": ["job_id", "limit", "offset"],
                "effect": "read",
                "required": ["job_id"],
                "returns": "A list of Steps ordered by stage.",
                "stage": "3",
                "summary": "Get the ordered job map for a Job.",
            },
            "get_jobs": {
                "arguments": ["limit", "offset"],
                "effect": "read",
                "required": [],
                "returns": "A list of Jobs.",
                "stage": "1",
                "summary": "List all Jobs.",
            },
            "get_odi_framework_guidelines": {
                "arguments": [],
                "effect": "read",
                "required": [],
                "returns": "The guidelines text.",
                "stage": None,
                "summary": "Get the stage-by-stage ODI framework guide.",
            },
            "get_odi_schema": {
                "arguments": [],
                "effect": "read",
                "required": [],
                "returns": "The full JSON schema object.",
                "stage": None,
                "summary": "Get the canonical JSON schema for all ODI entities.",
            },
            "get_outcome": {
                "arguments": ["outcome_id"],
                "effect": "read",
                "required": ["outcome_id"],
                "returns": "The Outcome, or an error string if not found.",
                "stage": "2",
                "summary": "Get a single Outcome by ID.",
            },
            "get_outcomes": {
                "arguments": ["job_id", "limit", "offset", "sort", "step_id"],
                "effect": "read",
                "required": ["job_id"],
                "returns": "A list of Outcomes.",
                "stage": "2",
                "summary": "List desired Outcomes for a Job.",
            },
            "get_step": {
                "arguments": ["step_id"],
                "effect": "read",
                "required": ["step_id"],
                "returns": "The Step, or an error string if not found.",
                "stage": "3",
                "summary": "Get a single Step by ID.",
            },
            "list_customer_outcomes": {
                "arguments": ["job_id", "limit", "offset"],
                "effect": "read",
                "required": [],
                "returns": "A list of Customer Outcomes.",
                "stage": None,
                "summary": "List Customer Outcomes for a Job.",
            },
            "list_evidence": {
                "arguments": ["job_id", "limit", "offset", "outcome_id", "step_id"],
                "effect": "read",
                "required": [],
                "returns": "A list of Evidence records.",
                "stage": None,
                "summary": "List evidence records, optionally filtered by job/step/outcome.",
            },
            "promote_evidence": {
                "arguments": [
                    "evidence_id",
                    "importance",
                    "job_id",
                    "name",
                    "satisfaction",
                    "statement",
                    "target",
                ],
                "effect": "write",
                "required": ["evidence_id", "target"],
                "returns": "The created Job or Outcome.",
                "stage": None,
                "summary": "Promote evidence to a Job or an Outcome.",
            },
            "update_customer_outcome": {
                "arguments": [
                    "business_statement",
                    "category",
                    "confidence",
                    "contextual_clarifier",
                    "detail",
                    "direction",
                    "estimated_annual_value",
                    "importance",
                    "object_of_control",
                    "outcome_id",
                    "satisfaction",
                    "statement",
                    "step_id",
                    "unit_of_measure",
                    "value_metrics",
                ],
                "effect": "write",
                "required": ["outcome_id"],
                "returns": "The updated Customer Outcome.",
                "stage": None,
                "summary": "Update a Customer Outcome's value metrics.",
            },
            "update_job": {
                "arguments": ["description", "job_id", "name"],
                "effect": "write",
                "required": ["job_id"],
                "returns": "The updated Job.",
                "stage": "1",
                "summary": "Update a Job's name or description.",
            },
            "update_outcome": {
                "arguments": ["importance", "outcome_id", "satisfaction", "statement", "step_id"],
                "effect": "write",
                "required": ["outcome_id"],
                "returns": "The updated Outcome.",
                "stage": "2",
                "summary": "Update an Outcome's statement or scores.",
            },
            "update_step": {
                "arguments": ["name", "order", "step_id"],
                "effect": "write",
                "required": ["step_id"],
                "returns": "The updated Step.",
                "stage": "3",
                "summary": "Update a Step's name or order.",
            },
        }
    )


def test_entity_schema_snapshot() -> None:
    assert _normalize(odi_schema()) == snapshot(
        {
            "BusinessValue": {
                "$defs": {
                    "BusinessImpactCategory": {
                        "enum": [
                            "brand_reputation",
                            "compliance",
                            "cost_reduction",
                            "operational_efficiency",
                            "other",
                            "retention",
                            "revenue_growth",
                            "risk_mitigation",
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
                        "anyOf": [{"type": "null"}, {"type": "string"}],
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
                            "brand_reputation",
                            "compliance",
                            "cost_reduction",
                            "operational_efficiency",
                            "other",
                            "retention",
                            "revenue_growth",
                            "risk_mitigation",
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
                                "anyOf": [{"type": "null"}, {"type": "string"}],
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
                                "anyOf": [{"type": "null"}, {"type": "string"}],
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
                            "importance",
                            "object_of_control",
                            "satisfaction",
                            "statement",
                            "unit_of_measure",
                        ],
                        "title": "CustomerValue",
                        "type": "object",
                    },
                    "Direction": {
                        "enum": ["maximize", "minimize"],
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
                            "direction",
                            "importance",
                            "name",
                            "satisfaction",
                            "unit_of_measure",
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
                    "step_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The ID of the specific Step, if applicable",
                        "title": "Step Id",
                    },
                },
                "required": ["business_value", "customer_value", "job_id"],
                "title": "CustomerOutcome",
                "type": "object",
            },
            "CustomerValue": {
                "$defs": {
                    "Direction": {
                        "enum": ["maximize", "minimize"],
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
                            "direction",
                            "importance",
                            "name",
                            "satisfaction",
                            "unit_of_measure",
                        ],
                        "title": "ValueMetric",
                        "type": "object",
                    },
                },
                "properties": {
                    "contextual_clarifier": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
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
                    "importance",
                    "object_of_control",
                    "satisfaction",
                    "statement",
                    "unit_of_measure",
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
                        "enum": ["catalog", "manual", "note", "resource", "tool_result"],
                        "title": "Item Type",
                        "type": "string",
                    },
                    "job_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "Job this evidence supports",
                        "title": "Job Id",
                    },
                    "name": {
                        "description": "Short human-readable label for the record",
                        "title": "Name",
                        "type": "string",
                    },
                    "outcome_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
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
                        "description": "Connector kind, e.g. mcp, rest, webhook, manual",
                        "title": "Source Kind",
                        "type": "string",
                    },
                    "source_name": {
                        "description": "Connector or person that produced the record",
                        "title": "Source Name",
                        "type": "string",
                    },
                    "step_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "Job-map Step this evidence supports",
                        "title": "Step Id",
                    },
                },
                "required": ["content", "name", "source_kind", "source_name"],
                "title": "Evidence",
                "type": "object",
            },
            "Job": {
                "properties": {
                    "description": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "Detailed description of the Job",
                        "title": "Description",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "name": {
                        "description": "The name of the Job-to-be-Done",
                        "title": "Name",
                        "type": "string",
                    },
                },
                "required": ["name"],
                "title": "Job",
                "type": "object",
            },
            "Outcome": {
                "properties": {
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
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                        "description": "Opportunity score (Importance + max(Importance - Satisfaction, 0))",
                        "title": "Opportunity Score",
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
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The ID of the specific Step, if applicable",
                        "title": "Step Id",
                    },
                },
                "required": ["job_id", "statement"],
                "title": "Outcome",
                "type": "object",
            },
            "Step": {
                "$defs": {
                    "JobStage": {
                        "description": "Ulwick's Universal Job Map stages, in canonical order.",
                        "enum": [
                            "conclude",
                            "confirm",
                            "define",
                            "execute",
                            "locate",
                            "modify",
                            "monitor",
                            "prepare",
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
            "ValueMetric": {
                "$defs": {
                    "Direction": {
                        "enum": ["maximize", "minimize"],
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
                "required": ["direction", "importance", "name", "satisfaction", "unit_of_measure"],
                "title": "ValueMetric",
                "type": "object",
            },
        }
    )
