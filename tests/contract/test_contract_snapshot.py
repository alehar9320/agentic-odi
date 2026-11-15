"""Pin the MCP and entity contract, so an accidental change fails CI instead of a customer.

The contract has three surfaces, and they can drift apart in three different ways:
the declared ``TOOL_SPECS`` in core, the input schemas the live MCP registry
actually serves, and ``odi_schema()`` for the entities those tools move around.
Snapshotting only the declaration misses the gap between what is declared and what
the server offers, so all three are pinned here together.

What gets pinned is structure: the arguments a tool takes, which of them are
required, its read/write effect, its ODI stage, and the JSON-schema shape of every
entity field. The wording is not pinned — not the tool summaries, not the field
descriptions. A reworded docstring is not a contract change, and a gate that fails on
one teaches people to regenerate without reading, which is how a gate dies. Prose is
reviewed in the diff of ``contract.py`` and ``schema.py``, where it is written.

A pinned surface is reviewed like code: the expected value sits in this file, and a
pull request that changes it shows exactly which tool argument, requiredness flag or
entity field moved.

When you *mean* to change the contract, regenerate deliberately and read the diff:

    uv run pytest tests/contract/test_contract_snapshot.py --inline-snapshot=create

Then re-run it plain to prove the new snapshot is what the code produces:

    uv run pytest tests/contract -k snapshot

CI only ever runs the plain command. ``--inline-snapshot=create`` rewrites this file,
which is the opposite of a gate, so it must never appear in a workflow.

Nothing here touches the network or a credential: the live registry is read in-process
through FastMCP's own client, the way ``test_mcp_contract.py`` reads it.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from typing import Any

import anyio
from agentic_odi_core.contract import TOOL_SPECS
from agentic_odi_core.schema import odi_schema
from agentic_odi_mcp_server.mcp_server import mcp
from fastmcp import Client
from inline_snapshot import snapshot

PROSE_KEYS = ("description", "title")


def _ordered(value: Any) -> Any:
    """Sort mapping keys and lists of names, so the pinned text is stable.

    Only ordering is normalized. Types, defaults and requiredness keep their meaning:
    a snapshot that quietly dropped them would pass a change it exists to catch.
    """
    if isinstance(value, Mapping):
        return {key: _ordered(value[key]) for key in sorted(value, key=repr)}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_ordered(item) for item in value]
        if all(isinstance(original, str) for original in value):
            items.sort()
        return items
    return value


def _structure(value: Any) -> Any:
    """Drop the wording from a JSON-schema view, keeping everything a caller can depend on.

    Only a wording key whose value is a sentence goes. An argument can be spelled
    exactly like a docstring field — ``add_job`` really does take ``description`` — and
    dropping the schema for it would silently delete part of the contract.
    """
    if isinstance(value, Mapping):
        return {
            key: _structure(value[key])
            for key in sorted(value, key=repr)
            if not (key in PROSE_KEYS and isinstance(value[key], str))
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_structure(item) for item in value]
    return value


def declared_contract(specs: Mapping[str, Any] = TOOL_SPECS) -> dict[str, Any]:
    """The declared side of the contract: the shape core promises for each tool."""
    return _ordered(
        {
            name: {
                "arguments": list(spec.arguments),
                "effect": spec.effect.value,
                "required": list(spec.required),
                "stage": spec.stage,
            }
            for name, spec in specs.items()
        }
    )


def live_registry() -> dict[str, Any]:
    """The served side of the contract: the input schemas the MCP server offers."""

    async def collect() -> dict[str, Any]:
        async with Client(mcp) as client:
            return {tool.name: tool.input_schema for tool in await client.list_tools()}

    return _ordered(_structure(anyio.run(collect)))


def entity_schema() -> dict[str, Any]:
    """The entity side of the contract: the shape every tool's payload claims."""
    return _ordered(_structure(odi_schema()))


def argument_names(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Project a served JSON-schema view down to the two facts the declaration also states."""
    properties = schema.get("properties", {})
    return _ordered(
        {
            "arguments": sorted(properties),
            "required": sorted(schema.get("required", [])),
        }
    )


def callable_shape(view: Mapping[str, Any]) -> dict[str, Any]:
    """Project a declared tool down to the same two facts the served schema states."""
    return _ordered(
        {
            "arguments": sorted(view["arguments"]),
            "required": sorted(view["required"]),
        }
    )


def drift(expected: Any, actual: Any, path: str = "contract") -> list[str]:
    """Name every difference between two contract views, one readable line each.

    This is what a person sees when the gate stops them, so it says which path moved
    and both sides of the change, rather than failing on a 900-line dict comparison.
    A string is a leaf here, not a sequence: comparing character by character would
    report a type change as "lost ['s'], gained ['e', 'e']".
    """
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        found: list[str] = []
        for key in sorted(set(expected) | set(actual), key=repr):
            if key not in expected:
                found.append(f"{path}.{key}: added")
            elif key not in actual:
                found.append(f"{path}.{key}: removed")
            else:
                found.extend(drift(expected[key], actual[key], f"{path}.{key}"))
        return found
    sequences = (list, tuple, set, frozenset)
    if isinstance(expected, sequences) and isinstance(actual, sequences):
        if list(expected) != list(actual):
            gone = [item for item in expected if item not in actual]
            new = [item for item in actual if item not in expected]
            parts = []
            if gone:
                parts.append(f"lost {gone}")
            if new:
                parts.append(f"gained {new}")
            detail = ", ".join(parts) if parts else f"{list(expected)} → {list(actual)}"
            return [f"{path}: {detail}"]
        return []
    if expected != actual:
        return [f"{path}: {expected!r} → {actual!r}"]
    return []


# --- the three pinned surfaces -------------------------------------------------


def test_declared_contract_is_pinned() -> None:
    assert declared_contract() == snapshot(
        {
            "add_customer_outcome": {
                "arguments": ["business_value", "customer_value", "job_id", "step_id"],
                "effect": "write",
                "required": ["business_value", "customer_value", "job_id"],
                "stage": None,
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
                    "url",
                ],
                "effect": "write",
                "required": ["content", "name", "source_kind", "source_name"],
                "stage": None,
            },
            "add_job": {
                "arguments": ["description", "name"],
                "effect": "write",
                "required": ["name"],
                "stage": "1",
            },
            "add_outcome": {
                "arguments": [
                    "claim_check",
                    "importance",
                    "job_id",
                    "satisfaction",
                    "statement",
                    "step_id",
                ],
                "effect": "write",
                "required": ["job_id", "statement"],
                "stage": "2",
            },
            "add_step": {
                "arguments": ["allow_empty_job_map", "job_id", "name", "order", "stage"],
                "effect": "write",
                "required": ["job_id", "name", "order"],
                "stage": "3",
            },
            "approve_proposal": {
                "arguments": ["importance", "proposal_id", "satisfaction", "statement"],
                "effect": "write",
                "required": ["proposal_id"],
                "stage": "2",
            },
            "cancel_scheduled_work": {
                "arguments": ["work_id"],
                "effect": "write",
                "required": ["work_id"],
                "stage": None,
            },
            "compute_opportunity": {
                "arguments": ["importance", "satisfaction"],
                "effect": "read",
                "required": ["importance", "satisfaction"],
                "stage": "4",
            },
            "delete_customer_outcome": {
                "arguments": ["outcome_id"],
                "effect": "destructive",
                "required": ["outcome_id"],
                "stage": None,
            },
            "delete_evidence": {
                "arguments": ["evidence_id"],
                "effect": "destructive",
                "required": ["evidence_id"],
                "stage": None,
            },
            "delete_job": {
                "arguments": ["job_id"],
                "effect": "destructive",
                "required": ["job_id"],
                "stage": "1",
            },
            "delete_outcome": {
                "arguments": ["outcome_id"],
                "effect": "destructive",
                "required": ["outcome_id"],
                "stage": "2",
            },
            "delete_step": {
                "arguments": ["step_id"],
                "effect": "destructive",
                "required": ["step_id"],
                "stage": "3",
            },
            "dismiss_signal": {
                "arguments": ["signal_id"],
                "effect": "write",
                "required": ["signal_id"],
                "stage": None,
            },
            "evaluate_outcome": {
                "arguments": ["job_id", "statement"],
                "effect": "read",
                "required": ["statement"],
                "stage": "2",
            },
            "get_capabilities": {"arguments": [], "effect": "read", "required": [], "stage": None},
            "get_capabilities_manifest": {
                "arguments": [],
                "effect": "read",
                "required": [],
                "stage": None,
            },
            "get_customer_outcome": {
                "arguments": ["outcome_id"],
                "effect": "read",
                "required": ["outcome_id"],
                "stage": None,
            },
            "get_evidence": {
                "arguments": ["evidence_id"],
                "effect": "read",
                "required": ["evidence_id"],
                "stage": None,
            },
            "get_health": {"arguments": [], "effect": "read", "required": [], "stage": None},
            "get_job": {
                "arguments": ["job_id"],
                "effect": "read",
                "required": ["job_id"],
                "stage": "1",
            },
            "get_job_map": {
                "arguments": ["job_id", "limit", "offset"],
                "effect": "read",
                "required": ["job_id"],
                "stage": "3",
            },
            "get_jobs": {
                "arguments": ["limit", "offset"],
                "effect": "read",
                "required": [],
                "stage": "1",
            },
            "get_odi_framework_guidelines": {
                "arguments": [],
                "effect": "read",
                "required": [],
                "stage": None,
            },
            "get_odi_schema": {"arguments": [], "effect": "read", "required": [], "stage": None},
            "get_outcome": {
                "arguments": ["outcome_id"],
                "effect": "read",
                "required": ["outcome_id"],
                "stage": "2",
            },
            "get_outcome_alignments": {
                "arguments": ["outcome_id"],
                "effect": "read",
                "required": [],
                "stage": "6",
            },
            "get_outcomes": {
                "arguments": ["job_id", "limit", "offset", "sort", "step_id"],
                "effect": "read",
                "required": ["job_id"],
                "stage": "2",
            },
            "get_scheduled_work": {
                "arguments": ["work_id"],
                "effect": "read",
                "required": ["work_id"],
                "stage": None,
            },
            "get_segments": {
                "arguments": ["job_id"],
                "effect": "read",
                "required": [],
                "stage": "5",
            },
            "get_step": {
                "arguments": ["step_id"],
                "effect": "read",
                "required": ["step_id"],
                "stage": "3",
            },
            "get_strategy": {"arguments": [], "effect": "read", "required": [], "stage": "6"},
            "get_traceability_report": {
                "arguments": [],
                "effect": "read",
                "required": [],
                "stage": "6",
            },
            "link_outcome": {
                "arguments": ["field", "outcome_id", "text"],
                "effect": "write",
                "required": ["field", "outcome_id", "text"],
                "stage": "6",
            },
            "list_customer_outcomes": {
                "arguments": ["job_id", "limit", "offset"],
                "effect": "read",
                "required": [],
                "stage": None,
            },
            "list_evidence": {
                "arguments": ["job_id", "limit", "offset", "outcome_id", "step_id"],
                "effect": "read",
                "required": [],
                "stage": None,
            },
            "list_proposals": {
                "arguments": ["status"],
                "effect": "read",
                "required": [],
                "stage": "2",
            },
            "list_scheduled_work": {
                "arguments": ["job_id", "status"],
                "effect": "read",
                "required": [],
                "stage": None,
            },
            "list_signals": {
                "arguments": ["limit", "unread_only"],
                "effect": "read",
                "required": [],
                "stage": None,
            },
            "list_studies": {
                "arguments": ["job_id"],
                "effect": "read",
                "required": [],
                "stage": None,
            },
            "mark_signal_read": {
                "arguments": ["signal_id"],
                "effect": "write",
                "required": ["signal_id"],
                "stage": None,
            },
            "open_study": {
                "arguments": ["job_id", "method_notes", "name", "wave"],
                "effect": "write",
                "required": ["job_id", "name", "wave"],
                "stage": None,
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
                "stage": None,
            },
            "propose_outcome": {
                "arguments": ["evidence_id"],
                "effect": "write",
                "required": ["evidence_id"],
                "stage": "2",
            },
            "propose_strategy": {
                "arguments": ["job_id"],
                "effect": "write",
                "required": [],
                "stage": "6",
            },
            "reject_proposal": {
                "arguments": ["proposal_id"],
                "effect": "write",
                "required": ["proposal_id"],
                "stage": "2",
            },
            "schedule_work": {
                "arguments": [
                    "agent_id",
                    "job_id",
                    "name",
                    "payload",
                    "schedule_expression",
                    "trigger_type",
                ],
                "effect": "write",
                "required": ["name", "schedule_expression"],
                "stage": None,
            },
            "segment_market": {
                "arguments": ["job_id", "people"],
                "effect": "write",
                "required": [],
                "stage": "5",
            },
            "trigger_scheduled_work": {
                "arguments": ["work_id"],
                "effect": "write",
                "required": ["work_id"],
                "stage": None,
            },
            "unlink_outcome": {
                "arguments": ["field", "key", "outcome_id"],
                "effect": "write",
                "required": ["field", "key", "outcome_id"],
                "stage": "6",
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
                "stage": None,
            },
            "update_job": {
                "arguments": ["description", "job_id", "name"],
                "effect": "write",
                "required": ["job_id"],
                "stage": "1",
            },
            "update_outcome": {
                "arguments": ["importance", "outcome_id", "satisfaction", "statement", "step_id"],
                "effect": "write",
                "required": ["outcome_id"],
                "stage": "2",
            },
            "update_step": {
                "arguments": ["name", "order", "step_id"],
                "effect": "write",
                "required": ["step_id"],
                "stage": "3",
            },
        }
    )


def test_live_registry_is_pinned() -> None:
    assert live_registry() == snapshot(
        {
            "add_customer_outcome": {
                "additionalProperties": False,
                "properties": {
                    "business_value": {"additionalProperties": True, "type": "object"},
                    "customer_value": {"additionalProperties": True, "type": "object"},
                    "job_id": {"type": "string"},
                    "step_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
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
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "name": {"type": "string"},
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
                "required": ["content", "name", "source_kind", "source_name"],
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
                    "stage": {
                        "anyOf": [
                            {
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
                "required": ["field", "outcome_id", "text"],
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
                "required": ["field", "key", "outcome_id"],
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


def test_entity_schema_is_pinned() -> None:
    assert entity_schema() == snapshot(
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
                    },
                    "detail": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "estimated_annual_value": {
                        "anyOf": [{"minimum": 0.0, "type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "statement": {"type": "string"},
                },
                "required": ["category", "statement"],
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
                            },
                            "detail": {
                                "anyOf": [{"type": "string"}, {"type": "null"}],
                                "default": None,
                            },
                            "estimated_annual_value": {
                                "anyOf": [{"minimum": 0.0, "type": "number"}, {"type": "null"}],
                                "default": None,
                            },
                            "statement": {"type": "string"},
                        },
                        "required": ["category", "statement"],
                        "type": "object",
                    },
                    "CustomerValue": {
                        "properties": {
                            "contextual_clarifier": {
                                "anyOf": [{"type": "string"}, {"type": "null"}],
                                "default": None,
                            },
                            "direction": {"$ref": "#/$defs/Direction"},
                            "importance": {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                            "object_of_control": {"type": "string"},
                            "satisfaction": {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                            "statement": {"type": "string"},
                            "unit_of_measure": {"type": "string"},
                            "value_metrics": {
                                "items": {"$ref": "#/$defs/ValueMetric"},
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
                        "type": "object",
                    },
                    "Direction": {"enum": ["maximize", "minimize"], "type": "string"},
                    "ValueMetric": {
                        "properties": {
                            "direction": {"$ref": "#/$defs/Direction"},
                            "importance": {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                            "name": {"type": "string"},
                            "satisfaction": {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                            "unit_of_measure": {"type": "string"},
                        },
                        "required": [
                            "direction",
                            "importance",
                            "name",
                            "satisfaction",
                            "unit_of_measure",
                        ],
                        "type": "object",
                    },
                },
                "properties": {
                    "business_value": {"$ref": "#/$defs/BusinessValue"},
                    "customer_value": {"$ref": "#/$defs/CustomerValue"},
                    "id": {"type": "string"},
                    "job_id": {"type": "string"},
                    "quote_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "step_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                },
                "required": ["business_value", "customer_value", "job_id"],
                "type": "object",
            },
            "CustomerValue": {
                "$defs": {
                    "Direction": {"enum": ["maximize", "minimize"], "type": "string"},
                    "ValueMetric": {
                        "properties": {
                            "direction": {"$ref": "#/$defs/Direction"},
                            "importance": {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                            "name": {"type": "string"},
                            "satisfaction": {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                            "unit_of_measure": {"type": "string"},
                        },
                        "required": [
                            "direction",
                            "importance",
                            "name",
                            "satisfaction",
                            "unit_of_measure",
                        ],
                        "type": "object",
                    },
                },
                "properties": {
                    "contextual_clarifier": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "direction": {"$ref": "#/$defs/Direction"},
                    "importance": {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                    "object_of_control": {"type": "string"},
                    "satisfaction": {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                    "statement": {"type": "string"},
                    "unit_of_measure": {"type": "string"},
                    "value_metrics": {"items": {"$ref": "#/$defs/ValueMetric"}, "type": "array"},
                },
                "required": [
                    "direction",
                    "importance",
                    "object_of_control",
                    "satisfaction",
                    "statement",
                    "unit_of_measure",
                ],
                "type": "object",
            },
            "Evidence": {
                "properties": {
                    "content": {"type": "string"},
                    "id": {"type": "string"},
                    "item_type": {
                        "default": "manual",
                        "enum": ["catalog", "manual", "note", "resource", "tool_result"],
                        "type": "string",
                    },
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "name": {"type": "string"},
                    "outcome_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "raw": {"additionalProperties": True, "type": "object"},
                    "source_kind": {"type": "string"},
                    "source_name": {"type": "string"},
                    "step_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "url": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                },
                "required": ["content", "name", "source_kind", "source_name"],
                "type": "object",
            },
            "Job": {
                "properties": {
                    "description": {
                        "anyOf": [{"maxLength": 500, "type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "id": {"type": "string"},
                    "name": {
                        "maxLength": 64,
                        "minLength": 3,
                        "pattern": "^[A-Za-z0-9 _-]+$",
                        "type": "string",
                    },
                },
                "required": ["name"],
                "type": "object",
            },
            "Outcome": {
                "$defs": {
                    "ClaimCheck": {
                        "properties": {
                            "answers": {"items": {"type": "string"}, "type": "array"},
                            "asked": {"items": {"type": "string"}, "type": "array"},
                            "skips": {"items": {"$ref": "#/$defs/ClaimSkip"}, "type": "array"},
                        },
                        "type": "object",
                    },
                    "ClaimSkip": {
                        "properties": {
                            "question": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["question", "reason"],
                        "type": "object",
                    },
                    "OutcomeAlignment": {
                        "properties": {
                            "field": {"enum": ["measure", "method"], "type": "string"},
                            "key": {"type": "string"},
                            "text": {"type": "string"},
                        },
                        "required": ["field", "key", "text"],
                        "type": "object",
                    },
                },
                "properties": {
                    "claim_check": {
                        "anyOf": [{"$ref": "#/$defs/ClaimCheck"}, {"type": "null"}],
                        "default": None,
                    },
                    "id": {"type": "string"},
                    "importance": {
                        "anyOf": [
                            {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                    "job_id": {"type": "string"},
                    "opportunity_score": {
                        "anyOf": [{"type": "number"}, {"type": "null"}],
                        "default": None,
                    },
                    "satisfaction": {
                        "anyOf": [
                            {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                    "statement": {"type": "string"},
                    "step_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "study_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "trace": {"items": {"$ref": "#/$defs/OutcomeAlignment"}, "type": "array"},
                },
                "required": ["job_id", "statement"],
                "type": "object",
            },
            "OutcomeAlignment": {
                "properties": {
                    "field": {"enum": ["measure", "method"], "type": "string"},
                    "key": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["field", "key", "text"],
                "type": "object",
            },
            "ScheduledWork": {
                "$defs": {
                    "ScheduledWorkStatus": {
                        "enum": [
                            "cancelled",
                            "completed",
                            "failed",
                            "pending",
                            "running",
                            "scheduled",
                        ],
                        "type": "string",
                    },
                    "ScheduledWorkTriggerType": {
                        "enum": ["cron", "interval", "oneshot"],
                        "type": "string",
                    },
                },
                "properties": {
                    "agent_id": {"default": "default-agent", "type": "string"},
                    "created_at": {"type": "string"},
                    "id": {"type": "string"},
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "last_run_at": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "name": {"type": "string"},
                    "next_run_at": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "payload": {"additionalProperties": True, "type": "object"},
                    "result_summary": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "schedule_expression": {"type": "string"},
                    "status": {"$ref": "#/$defs/ScheduledWorkStatus", "default": "scheduled"},
                    "trigger_type": {
                        "$ref": "#/$defs/ScheduledWorkTriggerType",
                        "default": "oneshot",
                    },
                },
                "required": ["name", "schedule_expression"],
                "type": "object",
            },
            "Segment": {
                "$defs": {
                    "SegmentVerdict": {
                        "enum": ["appropriately_served", "overserved", "underserved"],
                        "type": "string",
                    }
                },
                "properties": {
                    "computed_at_event_id": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "default": None,
                    },
                    "confidence": {"maximum": 1.0, "minimum": 0.0, "type": "number"},
                    "created_at": {"format": "date-time", "type": "string"},
                    "id": {"type": "string"},
                    "job_id": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    "job_statement": {"type": "string"},
                    "name": {"type": "string"},
                    "outcome_ids": {"items": {"type": "string"}, "type": "array"},
                    "people": {"type": "string"},
                    "people_inferred": {"default": False, "type": "boolean"},
                    "rationale": {"type": "string"},
                    "stale": {"anyOf": [{"type": "boolean"}, {"type": "null"}], "default": None},
                    "verdict": {
                        "anyOf": [{"$ref": "#/$defs/SegmentVerdict"}, {"type": "null"}],
                        "default": None,
                    },
                },
                "required": ["confidence", "job_statement", "name", "people", "rationale"],
                "type": "object",
            },
            "Step": {
                "$defs": {
                    "JobStage": {
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
                    }
                },
                "properties": {
                    "id": {"type": "string"},
                    "job_id": {"type": "string"},
                    "name": {"type": "string"},
                    "order": {"type": "integer"},
                    "stage": {
                        "anyOf": [{"$ref": "#/$defs/JobStage"}, {"type": "null"}],
                        "default": None,
                    },
                    "stage_index": {
                        "anyOf": [
                            {"maximum": 8, "minimum": 1, "type": "integer"},
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                },
                "required": ["job_id", "name", "order"],
                "type": "object",
            },
            "Strategy": {
                "$defs": {
                    "StrategyKind": {
                        "enum": ["differentiated", "disruptive", "new_market"],
                        "type": "string",
                    }
                },
                "properties": {
                    "bets": {"items": {"type": "string"}, "type": "array"},
                    "computed_at_event_id": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "default": None,
                    },
                    "created_at": {"format": "date-time", "type": "string"},
                    "id": {"type": "string"},
                    "kind": {"$ref": "#/$defs/StrategyKind"},
                    "rejected": {
                        "items": {"additionalProperties": True, "type": "object"},
                        "type": "array",
                    },
                    "segment_id": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "stale": {"anyOf": [{"type": "boolean"}, {"type": "null"}], "default": None},
                    "thesis": {"type": "string"},
                },
                "required": ["kind", "thesis"],
                "type": "object",
            },
            "Study": {
                "$defs": {
                    "StudyStatus": {"enum": ["closed", "fielding", "planned"], "type": "string"}
                },
                "properties": {
                    "closed_at": {
                        "anyOf": [{"format": "date-time", "type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "id": {"type": "string"},
                    "job_id": {"type": "string"},
                    "method_notes": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "default": None,
                    },
                    "name": {"type": "string"},
                    "opened_at": {"format": "date-time", "type": "string"},
                    "status": {"$ref": "#/$defs/StudyStatus", "default": "planned"},
                    "wave": {"minimum": 1, "type": "integer"},
                },
                "required": ["job_id", "name", "wave"],
                "type": "object",
            },
            "V2MOM": {
                "properties": {
                    "measures": {"items": {"type": "string"}, "type": "array"},
                    "methods": {"items": {"type": "string"}, "type": "array"},
                    "obstacles": {"items": {"type": "string"}, "type": "array"},
                    "values": {"items": {"type": "string"}, "type": "array"},
                    "vision": {"default": "", "type": "string"},
                },
                "type": "object",
            },
            "ValueMetric": {
                "$defs": {"Direction": {"enum": ["maximize", "minimize"], "type": "string"}},
                "properties": {
                    "direction": {"$ref": "#/$defs/Direction"},
                    "importance": {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                    "name": {"type": "string"},
                    "satisfaction": {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                    "unit_of_measure": {"type": "string"},
                },
                "required": ["direction", "importance", "name", "satisfaction", "unit_of_measure"],
                "type": "object",
            },
        }
    )


# --- the two views must describe the same tools --------------------------------


def test_declaration_and_registry_agree_on_every_tool() -> None:
    """A tool whose served arguments differ from the declared ones is caught here.

    Both surfaces are pinned above, so a change that updates one and not the other
    fails a pin. A change that updates both in the same wrong way still fails here,
    on the one comparison that spans the two: arguments and requiredness, which is
    all a caller can observe and all the declaration claims about them.
    """
    served = {name: argument_names(schema) for name, schema in live_registry().items()}
    declared = {name: callable_shape(view) for name, view in declared_contract().items()}
    assert drift(declared, served) == []


# --- the gate must be able to say no -------------------------------------------


def test_an_argument_named_description_survives_the_prose_filter() -> None:
    """The wording filter must not eat a real argument.

    ``add_job`` takes a parameter called ``description``, spelled exactly like the
    JSON-schema key this file strips. Dropping it would delete an argument from the
    pin and call that a simplification.
    """
    served = argument_names(live_registry()["add_job"])

    assert "description" in served["arguments"]
    assert "description" in _structure(odi_schema()["Job"]["properties"])


def test_renaming_a_tool_argument_is_reported_as_a_rename() -> None:
    """Proof the gate can fail: a rename is named on both sides, not shrugged at."""
    before = _ordered({"add_job": {"arguments": ["description", "name"], "required": ["name"]}})
    after = _ordered({"add_job": {"arguments": ["description", "label"], "required": ["label"]}})

    assert drift(before, after) == [
        "contract.add_job.arguments: lost ['name'], gained ['label']",
        "contract.add_job.required: lost ['name'], gained ['label']",
    ]


def test_making_an_argument_required_is_reported() -> None:
    """Proof the gate can fail: an argument that stopped being optional is named."""
    before = _ordered({"add_job": {"required": ["name"]}})
    after = _ordered({"add_job": {"required": ["description", "name"]}})

    assert drift(before, after) == ["contract.add_job.required: gained ['description']"]


def test_changing_an_entity_field_type_is_reported() -> None:
    """Proof the gate can fail: a field that changed type is named with both sides."""
    before = _structure({"Job": {"properties": {"name": {"type": "string"}}, "required": ["name"]}})
    after = _structure({"Job": {"properties": {"name": {"type": "integer"}}, "required": ["name"]}})

    assert drift(before, after) == ["contract.Job.properties.name.type: 'string' → 'integer'"]


def test_a_tool_only_the_registry_has_is_reported() -> None:
    """Proof the gate can fail: a tool served without being declared is named."""
    before = _ordered({"add_job": {"arguments": ["name"]}})
    after = _ordered({"add_job": {"arguments": ["name"]}, "forget_job": {"arguments": ["job_id"]}})

    assert drift(before, after) == ["contract.forget_job: added"]


def test_a_tool_the_registry_lost_is_reported() -> None:
    """Proof the gate can fail: a tool that stopped being served is named."""
    before = _ordered({"add_job": {"arguments": ["name"]}, "forget_job": {"arguments": ["job_id"]}})
    after = _ordered({"add_job": {"arguments": ["name"]}})

    assert drift(before, after) == ["contract.forget_job: removed"]


# --- generation does not depend on iteration order ----------------------------


def test_pinned_text_is_the_same_whatever_order_the_sources_come_in() -> None:
    """The snapshot must not churn because a dict or a registry listing reordered."""
    baseline = declared_contract()
    for seed in range(4):
        items = list(TOOL_SPECS.items())
        random.Random(seed).shuffle(items)
        assert declared_contract(dict(items)) == baseline
    entities = odi_schema()
    shuffled = list(entities.items())
    random.Random(7).shuffle(shuffled)
    assert _ordered(_structure(dict(shuffled))) == entity_schema()
    assert live_registry() == live_registry()
