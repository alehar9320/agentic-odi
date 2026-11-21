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
            "accept_candidate": {
                "additionalProperties": False,
                "properties": {
                    "candidate_id": {"type": "string"},
                    "importance": {"type": "number"},
                    "satisfaction": {"type": "number"},
                    "statement": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "step_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
                "required": ["candidate_id", "importance", "satisfaction"],
                "type": "object",
            },
            "add_alternative": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"type": "string"},
                    "kind": {"type": "string"},
                    "name": {"type": "string"},
                    "notes": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "source_kind": {"default": "manual", "type": "string"},
                },
                "required": ["job_id", "kind", "name"],
                "type": "object",
            },
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
                    "confidence": {"default": "claimed", "type": "string"},
                    "content": {"type": "string"},
                    "impact": {"default": "medium", "type": "string"},
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
                    "url": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
                "required": ["content", "name", "source_kind", "source_name"],
                "type": "object",
            },
            "add_interview": {
                "additionalProperties": False,
                "properties": {
                    "conducted_at": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "notes": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "participant_label": {"type": "string"},
                    "participant_role": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "source_kind": {"default": "manual", "type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["participant_label", "title"],
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
                    "claim_check": {
                        "anyOf": [
                            {"additionalProperties": True, "type": "object"},
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                    "importance": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                    },
                    "importance_n": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "default": None,
                    },
                    "job_id": {"type": "string"},
                    "note": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "objectives": {
                        "anyOf": [
                            {
                                "items": {
                                    "additionalProperties": {"type": "string"},
                                    "type": "object",
                                },
                                "type": "array",
                            },
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                    "satisfaction": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                    },
                    "satisfaction_n": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "default": None,
                    },
                    "score_method": {
                        "default": "estimate",
                        "enum": ["estimate", "import", "survey"],
                        "type": "string",
                    },
                    "statement": {"type": "string"},
                    "step_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
                "required": ["job_id", "statement"],
                "type": "object",
            },
            "add_quote": {
                "additionalProperties": False,
                "properties": {
                    "end_ms": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "interview_id": {"type": "string"},
                    "speaker": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "start_ms": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "text": {"type": "string"},
                },
                "required": ["interview_id", "text"],
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
            "approve_proposal": {
                "additionalProperties": False,
                "properties": {
                    "importance": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                    },
                    "proposal_id": {"type": "string"},
                    "satisfaction": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                    },
                    "statement": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
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
            "commit_survey_import": {
                "additionalProperties": False,
                "properties": {
                    "confirmed_matches": {
                        "anyOf": [
                            {"additionalProperties": {"type": "string"}, "type": "object"},
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                    "rows": {
                        "items": {"additionalProperties": True, "type": "object"},
                        "type": "array",
                    },
                },
                "required": ["rows"],
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
            "delete_alternative": {
                "additionalProperties": False,
                "properties": {"alternative_id": {"type": "string"}},
                "required": ["alternative_id"],
                "type": "object",
            },
            "delete_candidate": {
                "additionalProperties": False,
                "properties": {"candidate_id": {"type": "string"}},
                "required": ["candidate_id"],
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
            "delete_interview": {
                "additionalProperties": False,
                "properties": {"interview_id": {"type": "string"}},
                "required": ["interview_id"],
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
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "statement": {"type": "string"},
                },
                "required": ["statement"],
                "type": "object",
            },
            "extract_candidates": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "job_name": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "quote": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "quote_id": {"type": "string"},
                    "stage_hint": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                },
                "required": ["quote_id"],
                "type": "object",
            },
            "get_alternative": {
                "additionalProperties": False,
                "properties": {"alternative_id": {"type": "string"}},
                "required": ["alternative_id"],
                "type": "object",
            },
            "get_brief": {
                "additionalProperties": False,
                "properties": {"subject_id": {"type": "string"}},
                "required": ["subject_id"],
                "type": "object",
            },
            "get_candidate": {
                "additionalProperties": False,
                "properties": {"candidate_id": {"type": "string"}},
                "required": ["candidate_id"],
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
            "get_has_existing_solution": {
                "additionalProperties": False,
                "properties": {"outcome_id": {"type": "string"}},
                "required": ["outcome_id"],
                "type": "object",
            },
            "get_health": {"additionalProperties": False, "properties": {}, "type": "object"},
            "get_interview": {
                "additionalProperties": False,
                "properties": {"interview_id": {"type": "string"}},
                "required": ["interview_id"],
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
            "get_measurement": {
                "additionalProperties": False,
                "properties": {"bet_id": {"type": "string"}},
                "required": ["bet_id"],
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
                    "outcome_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None}
                },
                "type": "object",
            },
            "get_outcome_alternatives": {
                "additionalProperties": False,
                "properties": {"outcome_id": {"type": "string"}},
                "required": ["outcome_id"],
                "type": "object",
            },
            "get_outcome_delta": {
                "additionalProperties": False,
                "properties": {
                    "outcome_id": {"type": "string"},
                    "since": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
                "required": ["outcome_id"],
                "type": "object",
            },
            "get_outcome_history": {
                "additionalProperties": False,
                "properties": {"outcome_id": {"type": "string"}},
                "required": ["outcome_id"],
                "type": "object",
            },
            "get_outcome_inputs": {
                "additionalProperties": False,
                "properties": {"outcome_id": {"type": "string"}},
                "required": ["outcome_id"],
                "type": "object",
            },
            "get_outcome_interval": {
                "additionalProperties": False,
                "properties": {"outcome_id": {"type": "string"}},
                "required": ["outcome_id"],
                "type": "object",
            },
            "get_outcome_score": {
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
            "get_scheduled_work": {
                "additionalProperties": False,
                "properties": {"work_id": {"type": "string"}},
                "required": ["work_id"],
                "type": "object",
            },
            "get_segments": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None}
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
            "get_survey_import_plan": {
                "additionalProperties": False,
                "properties": {
                    "confirmed_matches": {
                        "anyOf": [
                            {"additionalProperties": {"type": "string"}, "type": "object"},
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                    "rows": {
                        "items": {"additionalProperties": True, "type": "object"},
                        "type": "array",
                    },
                },
                "required": ["rows"],
                "type": "object",
            },
            "get_traceability_report": {
                "additionalProperties": False,
                "properties": {},
                "type": "object",
            },
            "import_survey": {
                "additionalProperties": False,
                "properties": {
                    "rows": {
                        "items": {"additionalProperties": True, "type": "object"},
                        "type": "array",
                    }
                },
                "required": ["rows"],
                "type": "object",
            },
            "import_transcript": {
                "additionalProperties": False,
                "properties": {
                    "conducted_at": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "filename": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "format": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "participant_label": {"type": "string"},
                    "participant_role": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "text": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["participant_label", "text", "title"],
                "type": "object",
            },
            "link_alternative": {
                "additionalProperties": False,
                "properties": {
                    "adequacy": {"type": "number"},
                    "alternative_id": {"type": "string"},
                    "note": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "outcome_id": {"type": "string"},
                    "usage_n": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                },
                "required": ["adequacy", "alternative_id", "outcome_id"],
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
            "links_add": {
                "additionalProperties": False,
                "properties": {
                    "external_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "external_system": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "preview": {
                        "anyOf": [
                            {"additionalProperties": True, "type": "object"},
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                    "relationship_type": {"type": "string"},
                    "source_id": {"type": "string"},
                    "source_type": {"type": "string"},
                    "target_id": {"type": "string"},
                    "target_type": {"type": "string"},
                },
                "required": [
                    "relationship_type",
                    "source_id",
                    "source_type",
                    "target_id",
                    "target_type",
                ],
                "type": "object",
            },
            "links_list": {
                "additionalProperties": False,
                "properties": {
                    "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "offset": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "relationship_type": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "source_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "source_type": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "target_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "target_type": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                },
                "type": "object",
            },
            "links_remove": {
                "additionalProperties": False,
                "properties": {"link_id": {"type": "string"}},
                "required": ["link_id"],
                "type": "object",
            },
            "list_alternative_links": {
                "additionalProperties": False,
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
                "type": "object",
            },
            "list_alternatives": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "offset": {"default": 0, "type": "integer"},
                },
                "type": "object",
            },
            "list_candidates": {
                "additionalProperties": False,
                "properties": {
                    "interview_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "offset": {"default": 0, "type": "integer"},
                    "quote_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "status": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
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
            "list_interviews": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
                    "offset": {"default": 0, "type": "integer"},
                },
                "type": "object",
            },
            "list_proposals": {
                "additionalProperties": False,
                "properties": {
                    "status": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None}
                },
                "type": "object",
            },
            "list_quotes": {
                "additionalProperties": False,
                "properties": {"interview_id": {"type": "string"}},
                "required": ["interview_id"],
                "type": "object",
            },
            "list_scheduled_work": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "status": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
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
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None}
                },
                "type": "object",
            },
            "mark_signal_read": {
                "additionalProperties": False,
                "properties": {"signal_id": {"type": "string"}},
                "required": ["signal_id"],
                "type": "object",
            },
            "merge_candidate": {
                "additionalProperties": False,
                "properties": {
                    "candidate_id": {"type": "string"},
                    "merged_into": {"type": "string"},
                },
                "required": ["candidate_id", "merged_into"],
                "type": "object",
            },
            "open_study": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"type": "string"},
                    "method_notes": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
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
                    "force": {"default": False, "type": "boolean"},
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
            "propose_outcome": {
                "additionalProperties": False,
                "properties": {"evidence_id": {"type": "string"}},
                "required": ["evidence_id"],
                "type": "object",
            },
            "propose_strategy": {
                "additionalProperties": False,
                "properties": {
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None}
                },
                "type": "object",
            },
            "rank_outcomes": {
                "additionalProperties": False,
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
                "type": "object",
            },
            "record_decision": {
                "additionalProperties": False,
                "properties": {
                    "choice": {"type": "string"},
                    "rationale": {"type": "string"},
                    "subject_id": {"type": "string"},
                },
                "required": ["choice", "rationale", "subject_id"],
                "type": "object",
            },
            "reject_candidate": {
                "additionalProperties": False,
                "properties": {"candidate_id": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["candidate_id", "reason"],
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
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
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
                    "job_id": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "people": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
                "type": "object",
            },
            "track_bet": {
                "additionalProperties": False,
                "properties": {
                    "decision_id": {"type": "string"},
                    "metric": {"type": "string"},
                    "statement": {"type": "string"},
                },
                "required": ["decision_id", "metric", "statement"],
                "type": "object",
            },
            "trigger_scheduled_work": {
                "additionalProperties": False,
                "properties": {"work_id": {"type": "string"}},
                "required": ["work_id"],
                "type": "object",
            },
            "unlink_alternative": {
                "additionalProperties": False,
                "properties": {
                    "alternative_id": {"type": "string"},
                    "outcome_id": {"type": "string"},
                },
                "required": ["alternative_id", "outcome_id"],
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
            "update_candidate": {
                "additionalProperties": False,
                "properties": {
                    "candidate_id": {"type": "string"},
                    "decision_reason": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                    },
                    "statement": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "status": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                },
                "required": ["candidate_id"],
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
                    "importance_n": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "default": None,
                    },
                    "note": {"anyOf": [{"type": "null"}, {"type": "string"}], "default": None},
                    "objectives": {
                        "anyOf": [
                            {
                                "items": {
                                    "additionalProperties": {"type": "string"},
                                    "type": "object",
                                },
                                "type": "array",
                            },
                            {"type": "null"},
                        ],
                        "default": None,
                    },
                    "outcome_id": {"type": "string"},
                    "satisfaction": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                    },
                    "satisfaction_n": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "default": None,
                    },
                    "score_method": {
                        "anyOf": [
                            {"enum": ["estimate", "import", "survey"], "type": "string"},
                            {"type": "null"},
                        ],
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
            "accept_candidate": {
                "arguments": ["candidate_id", "importance", "satisfaction", "statement", "step_id"],
                "effect": "write",
                "required": ["candidate_id", "importance", "satisfaction"],
                "returns": "The created Outcome.",
                "stage": "2",
                "summary": "Accept a proposed outcome, creating exactly one Outcome.",
            },
            "add_alternative": {
                "arguments": ["job_id", "kind", "name", "notes", "source_kind"],
                "effect": "write",
                "required": ["job_id", "kind", "name"],
                "returns": "The created Alternative.",
                "stage": "2",
                "summary": "Record what a customer uses today for one Job.",
            },
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
                    "confidence",
                    "content",
                    "impact",
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
                "returns": "The created Evidence record.",
                "stage": None,
                "summary": "Capture an evidence record from a connector with optional impact and confidence ratings.",
            },
            "add_interview": {
                "arguments": [
                    "conducted_at",
                    "job_id",
                    "notes",
                    "participant_label",
                    "participant_role",
                    "source_kind",
                    "title",
                ],
                "effect": "write",
                "required": ["participant_label", "title"],
                "returns": "The created Interview.",
                "stage": None,
                "summary": "Record a research interview (who, when, the job it informs).",
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
                "arguments": [
                    "claim_check",
                    "importance",
                    "importance_n",
                    "job_id",
                    "note",
                    "objectives",
                    "satisfaction",
                    "satisfaction_n",
                    "score_method",
                    "statement",
                    "step_id",
                ],
                "effect": "write",
                "required": ["job_id", "statement"],
                "returns": "The created Outcome.",
                "stage": "2",
                "summary": "Add a desired Outcome to a Job; three questions and the person's answers come before any score, and the score carries them as a claim_check.",
            },
            "add_quote": {
                "arguments": ["end_ms", "interview_id", "speaker", "start_ms", "text"],
                "effect": "write",
                "required": ["interview_id", "text"],
                "returns": "The created InterviewQuote.",
                "stage": None,
                "summary": "Append a verbatim quote to an interview.",
            },
            "add_step": {
                "arguments": ["allow_empty_job_map", "job_id", "name", "order", "stage"],
                "effect": "write",
                "required": ["job_id", "name", "order"],
                "returns": "The created Step.",
                "stage": "3",
                "summary": "Add a step to a Job's job map.",
            },
            "approve_proposal": {
                "arguments": ["importance", "proposal_id", "satisfaction", "statement"],
                "effect": "write",
                "required": ["proposal_id"],
                "returns": "The created Outcome.",
                "stage": "2",
                "summary": "Approve a proposal and write it as an Outcome.",
            },
            "cancel_scheduled_work": {
                "arguments": ["work_id"],
                "effect": "write",
                "required": ["work_id"],
                "returns": "The cancelled scheduled work item.",
                "stage": None,
                "summary": "Cancel a scheduled work item.",
            },
            "commit_survey_import": {
                "arguments": ["confirmed_matches", "rows"],
                "effect": "write",
                "required": ["rows"],
                "returns": "The updated Outcomes keyed by id, or a refusal naming the unresolved rows.",
                "stage": "4",
                "summary": "Write a survey import only when every row resolves; otherwise refuse.",
            },
            "compute_opportunity": {
                "arguments": ["importance", "satisfaction"],
                "effect": "read",
                "required": ["importance", "satisfaction"],
                "returns": "The opportunity score as a float.",
                "stage": "4",
                "summary": "Compute an ODI opportunity score from importance and satisfaction.",
            },
            "delete_alternative": {
                "arguments": ["alternative_id"],
                "effect": "destructive",
                "required": ["alternative_id"],
                "returns": "The deleted Alternative ID.",
                "stage": "2",
                "summary": "Delete an Alternative and its links.",
            },
            "delete_candidate": {
                "arguments": ["candidate_id"],
                "effect": "destructive",
                "required": ["candidate_id"],
                "returns": "The deleted candidate ID.",
                "stage": None,
                "summary": "Delete an OutcomeCandidate.",
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
            "delete_interview": {
                "arguments": ["interview_id"],
                "effect": "destructive",
                "required": ["interview_id"],
                "returns": "The deleted Interview ID.",
                "stage": None,
                "summary": "Delete an Interview and its cascading quotes.",
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
            "dismiss_signal": {
                "arguments": ["signal_id"],
                "effect": "write",
                "required": ["signal_id"],
                "returns": "The updated Signal.",
                "stage": None,
                "summary": "Dismiss a signal; it stays recorded but leaves the feed.",
            },
            "evaluate_outcome": {
                "arguments": ["job_id", "statement"],
                "effect": "read",
                "required": ["statement"],
                "returns": "A verdict with coded issues and suggestions.",
                "stage": "2",
                "summary": "Evaluate an outcome statement against ODI format rules.",
            },
            "extract_candidates": {
                "arguments": ["job_id", "job_name", "quote", "quote_id", "stage_hint"],
                "effect": "write",
                "required": ["quote_id"],
                "returns": "The newly stored OutcomeCandidates (valid ones proposed, invalid ones rejected).",
                "stage": None,
                "summary": "Propose candidates from an interview quote, or raw text with a job.",
            },
            "get_alternative": {
                "arguments": ["alternative_id"],
                "effect": "read",
                "required": ["alternative_id"],
                "returns": "The Alternative, or an error string if not found.",
                "stage": "2",
                "summary": "Get a single Alternative by ID.",
            },
            "get_brief": {
                "arguments": ["subject_id"],
                "effect": "read",
                "required": ["subject_id"],
                "returns": "The brief document for the subject.",
                "stage": None,
                "summary": "Render the brief for a subject, each figure carrying its basis.",
            },
            "get_candidate": {
                "arguments": ["candidate_id"],
                "effect": "read",
                "required": ["candidate_id"],
                "returns": "The OutcomeCandidate, or an error string if not found.",
                "stage": None,
                "summary": "Get a single OutcomeCandidate by ID.",
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
            "get_has_existing_solution": {
                "arguments": ["outcome_id"],
                "effect": "read",
                "required": ["outcome_id"],
                "returns": "One of yes, no_linked_nothing, no_link_at_all.",
                "stage": "2",
                "summary": "Whether an existing solution is recorded: yes, nothing linked, or not asked.",
            },
            "get_health": {
                "arguments": [],
                "effect": "read",
                "required": [],
                "returns": '{"status": "ok", "store": "accessible"} or a degraded status.',
                "stage": None,
                "summary": "Check that the ODI store is reachable.",
            },
            "get_interview": {
                "arguments": ["interview_id"],
                "effect": "read",
                "required": ["interview_id"],
                "returns": "The Interview, or an error string if not found.",
                "stage": None,
                "summary": "Get a single Interview by ID.",
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
            "get_measurement": {
                "arguments": ["bet_id"],
                "effect": "read",
                "required": ["bet_id"],
                "returns": "The measurement for the bet.",
                "stage": None,
                "summary": "Read what a bet measured; an unmeasured bet reports nothing yet.",
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
            "get_outcome_alignments": {
                "arguments": ["outcome_id"],
                "effect": "read",
                "required": [],
                "returns": "A list of links, each naming the outcome, field, key, and text.",
                "stage": "6",
                "summary": "List the V2MOM links recorded on Outcomes.",
            },
            "get_outcome_alternatives": {
                "arguments": ["outcome_id"],
                "effect": "read",
                "required": ["outcome_id"],
                "returns": "A list of Alternatives paired with their adequacy link.",
                "stage": "2",
                "summary": "The Alternatives recorded for one Outcome, with each adequacy rating.",
            },
            "get_outcome_delta": {
                "arguments": ["outcome_id", "since"],
                "effect": "read",
                "required": ["outcome_id"],
                "returns": "The signed importance/satisfaction/opportunity deltas and a direction.",
                "stage": "4",
                "summary": "The signed score change across an Outcome's recorded snapshots.",
            },
            "get_outcome_history": {
                "arguments": ["outcome_id"],
                "effect": "read",
                "required": ["outcome_id"],
                "returns": "A list of score snapshots, oldest first.",
                "stage": "4",
                "summary": "List the accepted score snapshots for an Outcome, oldest first.",
            },
            "get_outcome_inputs": {
                "arguments": ["outcome_id"],
                "effect": "read",
                "required": ["outcome_id"],
                "returns": "The de-identified paired inputs and their versioned input ref, or null.",
                "stage": "4",
                "summary": "The paired survey inputs a stored band was reproduced from, or a no-inputs result.",
            },
            "get_outcome_interval": {
                "arguments": ["outcome_id"],
                "effect": "read",
                "required": ["outcome_id"],
                "returns": "The band's bounds, sample, seed, confidence, method, computed-at and staleness.",
                "stage": "4",
                "summary": "The stored band and its provenance for an Outcome, or a no-band result.",
            },
            "get_outcome_score": {
                "arguments": ["outcome_id"],
                "effect": "read",
                "required": ["outcome_id"],
                "returns": "The score sample for the outcome.",
                "stage": "4",
                "summary": "Read an outcome's scores as a sample, with its sample size.",
            },
            "get_outcomes": {
                "arguments": ["job_id", "limit", "offset", "sort", "step_id"],
                "effect": "read",
                "required": ["job_id"],
                "returns": "A list of Outcomes.",
                "stage": "2",
                "summary": "List desired Outcomes for a Job.",
            },
            "get_scheduled_work": {
                "arguments": ["work_id"],
                "effect": "read",
                "required": ["work_id"],
                "returns": "The scheduled work item, or an error string if not found.",
                "stage": None,
                "summary": "Get a scheduled work item by ID.",
            },
            "get_segments": {
                "arguments": ["job_id"],
                "effect": "read",
                "required": [],
                "returns": "A list of Segments. Empty until segment_market has run.",
                "stage": "5",
                "summary": "List the segments the market was divided into.",
            },
            "get_step": {
                "arguments": ["step_id"],
                "effect": "read",
                "required": ["step_id"],
                "returns": "The Step, or an error string if not found.",
                "stage": "3",
                "summary": "Get a single Step by ID.",
            },
            "get_strategy": {
                "arguments": [],
                "effect": "read",
                "required": [],
                "returns": "The Strategy with its rejected alternatives, or null if none was recorded.",
                "stage": "6",
                "summary": "Get the most recently recorded innovation strategy.",
            },
            "get_survey_import_plan": {
                "arguments": ["confirmed_matches", "rows"],
                "effect": "read",
                "required": ["rows"],
                "returns": "Per-row accepted/unmatched/ambiguous/invalid reports with line numbers.",
                "stage": "4",
                "summary": "Plan a survey import without writing: every row's fate and line number.",
            },
            "get_traceability_report": {
                "arguments": [],
                "effect": "read",
                "required": [],
                "returns": "The orphans, unfunded, and drift lists, or a note that no objectives exist.",
                "stage": "6",
                "summary": "Report orphans, unfunded objectives, and links the vision dropped.",
            },
            "import_survey": {
                "arguments": ["rows"],
                "effect": "write",
                "required": ["rows"],
                "returns": "The updated Outcomes keyed by id.",
                "stage": "4",
                "summary": "Land a survey's per-outcome means, sample and band on matching Outcomes.",
            },
            "import_transcript": {
                "arguments": [
                    "conducted_at",
                    "filename",
                    "format",
                    "job_id",
                    "participant_label",
                    "participant_role",
                    "text",
                    "title",
                ],
                "effect": "write",
                "required": ["participant_label", "text", "title"],
                "returns": "The created Interview and the number of quotes.",
                "stage": None,
                "summary": "Parse a transcript and persist it as one interview with its quotes.",
            },
            "link_alternative": {
                "arguments": ["adequacy", "alternative_id", "note", "outcome_id", "usage_n"],
                "effect": "write",
                "required": ["adequacy", "alternative_id", "outcome_id"],
                "returns": "The created Alternative link.",
                "stage": "2",
                "summary": "Rate one Alternative against one Outcome with the customer's adequacy.",
            },
            "link_outcome": {
                "arguments": ["field", "outcome_id", "text"],
                "effect": "write",
                "required": ["field", "outcome_id", "text"],
                "returns": "The updated Outcome, or a refusal naming the objectives that do exist.",
                "stage": "6",
                "summary": "Link an Outcome to the V2MOM method or measure it advances.",
            },
            "links_add": {
                "arguments": [
                    "external_id",
                    "external_system",
                    "preview",
                    "relationship_type",
                    "source_id",
                    "source_type",
                    "target_id",
                    "target_type",
                ],
                "effect": "write",
                "required": [
                    "relationship_type",
                    "source_id",
                    "source_type",
                    "target_id",
                    "target_type",
                ],
                "returns": "The created Link record.",
                "stage": None,
                "summary": "Create a typed link between two agentic-odi entities.",
            },
            "links_list": {
                "arguments": [
                    "limit",
                    "offset",
                    "relationship_type",
                    "source_id",
                    "source_type",
                    "target_id",
                    "target_type",
                ],
                "effect": "write",
                "required": [],
                "returns": "A list of Link records.",
                "stage": None,
                "summary": "List links, optionally filtered by source/target entity and relationship type.",
            },
            "links_remove": {
                "arguments": ["link_id"],
                "effect": "write",
                "required": ["link_id"],
                "returns": "True if the link was removed, False if not found.",
                "stage": None,
                "summary": "Remove a link by ID.",
            },
            "list_alternative_links": {
                "arguments": ["job_id"],
                "effect": "read",
                "required": ["job_id"],
                "returns": "A list of outcome/alternative/link triples for the whole Job.",
                "stage": "2",
                "summary": "Every recorded alternative for one Job, each with its outcome and adequacy.",
            },
            "list_alternatives": {
                "arguments": ["job_id", "limit", "offset"],
                "effect": "read",
                "required": [],
                "returns": "A list of Alternatives.",
                "stage": "2",
                "summary": "List the Alternatives recorded for a Job.",
            },
            "list_candidates": {
                "arguments": ["interview_id", "job_id", "limit", "offset", "quote_id", "status"],
                "effect": "read",
                "required": [],
                "returns": "A list of OutcomeCandidates.",
                "stage": None,
                "summary": "List candidates, filtered by interview, quote, job or status.",
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
            "list_interviews": {
                "arguments": ["job_id", "limit", "offset"],
                "effect": "read",
                "required": [],
                "returns": "A list of Interviews.",
                "stage": None,
                "summary": "List interviews, optionally filtered by job.",
            },
            "list_proposals": {
                "arguments": ["status"],
                "effect": "read",
                "required": [],
                "returns": "A list of OutcomeProposals.",
                "stage": "2",
                "summary": "List outcome proposals, optionally filtered by status.",
            },
            "list_quotes": {
                "arguments": ["interview_id"],
                "effect": "read",
                "required": ["interview_id"],
                "returns": "A list of InterviewQuotes ordered by ordinal.",
                "stage": None,
                "summary": "List an interview's quotes in ordinal order.",
            },
            "list_scheduled_work": {
                "arguments": ["job_id", "status"],
                "effect": "read",
                "required": [],
                "returns": "A list of scheduled work items.",
                "stage": None,
                "summary": "List scheduled work, optionally filtered by Job or status.",
            },
            "list_signals": {
                "arguments": ["limit", "unread_only"],
                "effect": "read",
                "required": [],
                "returns": "A list of Signals, newest first.",
                "stage": None,
                "summary": "List signals the store recorded — real changes worth attention.",
            },
            "list_studies": {
                "arguments": ["job_id"],
                "effect": "read",
                "required": [],
                "returns": "A list of Studies. Empty until a study has been opened.",
                "stage": None,
                "summary": "List the studies opened for a Job.",
            },
            "mark_signal_read": {
                "arguments": ["signal_id"],
                "effect": "write",
                "required": ["signal_id"],
                "returns": "The updated Signal.",
                "stage": None,
                "summary": "Mark a signal as read so it stops counting toward the unread badge.",
            },
            "merge_candidate": {
                "arguments": ["candidate_id", "merged_into"],
                "effect": "write",
                "required": ["candidate_id", "merged_into"],
                "returns": "The merged candidate.",
                "stage": "2",
                "summary": "Fold a proposed outcome into an existing Outcome; creates none.",
            },
            "open_study": {
                "arguments": ["job_id", "method_notes", "name", "wave"],
                "effect": "write",
                "required": ["job_id", "name", "wave"],
                "returns": "The created Study, opened as planned.",
                "stage": None,
                "summary": "Open a named study pass over a Job at a given wave number.",
            },
            "promote_evidence": {
                "arguments": [
                    "evidence_id",
                    "force",
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
            "propose_outcome": {
                "arguments": ["evidence_id"],
                "effect": "write",
                "required": ["evidence_id"],
                "returns": "An OutcomeProposal ready for human approval.",
                "stage": "2",
                "summary": "Propose a desired outcome mined from an evidence record.",
            },
            "propose_strategy": {
                "arguments": ["job_id"],
                "effect": "write",
                "required": [],
                "returns": "The Strategy, including every path it beat and why.",
                "stage": "6",
                "summary": "Recommend the one innovation path the segments support.",
            },
            "rank_outcomes": {
                "arguments": ["job_id"],
                "effect": "write",
                "required": ["job_id"],
                "returns": "The measured/thin/none sections with per-outcome score, band, sample and method.",
                "stage": "4",
                "summary": "Rank a Job's Outcomes by evidence strength into measured/thin/none sections.",
            },
            "record_decision": {
                "arguments": ["choice", "rationale", "subject_id"],
                "effect": "write",
                "required": ["choice", "rationale", "subject_id"],
                "returns": "The recorded decision.",
                "stage": None,
                "summary": "Record a decision about a subject, with its rationale.",
            },
            "reject_candidate": {
                "arguments": ["candidate_id", "reason"],
                "effect": "write",
                "required": ["candidate_id", "reason"],
                "returns": "The rejected candidate.",
                "stage": "2",
                "summary": "Reject a proposed outcome; a non-empty reason is required and kept.",
            },
            "reject_proposal": {
                "arguments": ["proposal_id"],
                "effect": "write",
                "required": ["proposal_id"],
                "returns": "The rejected OutcomeProposal.",
                "stage": "2",
                "summary": "Reject a proposal; nothing is written to the ODI store.",
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
                "returns": "The created scheduled work item.",
                "stage": None,
                "summary": "Schedule agent work with a cron or one-shot expression.",
            },
            "segment_market": {
                "arguments": ["job_id", "people"],
                "effect": "write",
                "required": [],
                "returns": "The segments the outcomes clustered into, with verdict and confidence.",
                "stage": "5",
                "summary": "Cluster the scored outcomes into outcome-based segments.",
            },
            "track_bet": {
                "arguments": ["decision_id", "metric", "statement"],
                "effect": "write",
                "required": ["decision_id", "metric", "statement"],
                "returns": "The tracked bet.",
                "stage": None,
                "summary": "Track a bet under a decision, with the metric that would move.",
            },
            "trigger_scheduled_work": {
                "arguments": ["work_id"],
                "effect": "write",
                "required": ["work_id"],
                "returns": "The dispatched scheduled work item.",
                "stage": None,
                "summary": "Dispatch a scheduled work item immediately.",
            },
            "unlink_alternative": {
                "arguments": ["alternative_id", "outcome_id"],
                "effect": "write",
                "required": ["alternative_id", "outcome_id"],
                "returns": "The removed link's identifiers.",
                "stage": "2",
                "summary": "Remove one Alternative-to-Outcome link.",
            },
            "unlink_outcome": {
                "arguments": ["field", "key", "outcome_id"],
                "effect": "write",
                "required": ["field", "key", "outcome_id"],
                "returns": "The updated Outcome.",
                "stage": "6",
                "summary": "Remove one V2MOM link from an Outcome.",
            },
            "update_candidate": {
                "arguments": ["candidate_id", "decision_reason", "statement", "status"],
                "effect": "write",
                "required": ["candidate_id"],
                "returns": "The updated OutcomeCandidate.",
                "stage": None,
                "summary": "Update an outcome candidate's review state or statement.",
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
                "arguments": [
                    "importance",
                    "importance_n",
                    "note",
                    "objectives",
                    "outcome_id",
                    "satisfaction",
                    "satisfaction_n",
                    "score_method",
                    "statement",
                    "step_id",
                ],
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
            "Alternative": {
                "description": """\
What a customer uses today for one Job (M2-07).

A competitor, a spreadsheet, a workaround, or nothing. Recorded so
"underserved" has something to be underserved relative to. An alternative is
never inferred from a score or created by an import: it is customer-provided.\
""",
                "properties": {
                    "id": {"title": "Id", "type": "string"},
                    "job_id": {
                        "description": "The ID of the Job this alternative serves",
                        "title": "Job Id",
                        "type": "string",
                    },
                    "kind": {
                        "description": "What kind of alternative this is",
                        "enum": ["manual", "nothing", "product", "service", "workaround"],
                        "title": "Kind",
                        "type": "string",
                    },
                    "name": {
                        "description": "Short human-readable label",
                        "minLength": 1,
                        "title": "Name",
                        "type": "string",
                    },
                    "notes": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "Customer-provided source notes, kept as text",
                        "title": "Notes",
                    },
                    "source_kind": {
                        "default": "manual",
                        "description": "Where the record came from; see ALTERNATIVE_SOURCE_KINDS (provisional)",
                        "title": "Source Kind",
                        "type": "string",
                    },
                },
                "required": ["job_id", "kind", "name"],
                "title": "Alternative",
                "type": "object",
            },
            "AlternativeLink": {
                "description": """\
A customer's adequacy rating for one alternative against one outcome (M2-07).

Adequacy belongs to the link, not the alternative: the same competitor is
adequate for one need and useless for another. The rating is the customer's
own, never derived from the opportunity score.\
""",
                "properties": {
                    "adequacy": {
                        "description": "How adequate the alternative is for the outcome (1-10)",
                        "maximum": 10.0,
                        "minimum": 1.0,
                        "title": "Adequacy",
                        "type": "number",
                    },
                    "alternative_id": {
                        "description": "The alternative this link rates",
                        "title": "Alternative Id",
                        "type": "string",
                    },
                    "note": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "Customer-provided note, kept as text",
                        "title": "Note",
                    },
                    "outcome_id": {
                        "description": "The outcome this link rates",
                        "title": "Outcome Id",
                        "type": "string",
                    },
                    "usage_n": {
                        "anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}],
                        "default": None,
                        "description": "People behind the rating, when known; unknown stays None",
                        "title": "Usage N",
                    },
                },
                "required": ["adequacy", "alternative_id", "outcome_id"],
                "title": "AlternativeLink",
                "type": "object",
            },
            "BetRecord": {
                "description": """\
A bet: a decision's claim, plus the metric that would move if it is right.

``baseline`` is ``None`` when the metric has not been measured yet — an
unknown baseline, not a measured zero.\
""",
                "properties": {
                    "baseline": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                        "description": "The metric's value before the bet, if known",
                        "title": "Baseline",
                    },
                    "decision_id": {
                        "description": "The Decision this bet tests",
                        "title": "Decision Id",
                        "type": "string",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "metric": {
                        "description": "The metric that would move",
                        "title": "Metric",
                        "type": "string",
                    },
                    "statement": {
                        "description": "The claim being bet on",
                        "title": "Statement",
                        "type": "string",
                    },
                },
                "required": ["decision_id", "metric", "statement"],
                "title": "BetRecord",
                "type": "object",
            },
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
            "CandidateSolution": {
                "$defs": {
                    "CandidateStatus": {
                        "description": "Where a candidate is in its life: proposed, accepted, rejected, or parked.",
                        "enum": ["accepted", "merged", "parked", "proposed", "rejected"],
                        "title": "CandidateStatus",
                        "type": "string",
                    },
                    "StrategyKind": {
                        "description": "Stage 6's three strategic paths.",
                        "enum": ["differentiated", "disruptive", "new_market"],
                        "title": "StrategyKind",
                        "type": "string",
                    },
                },
                "description": """\
A proposed solution linked to the underserved outcomes it would serve.

A candidate is the bridge from research to a bet: it names a hypothesis and
the outcomes that justify it. The model records the claim; the rule that a
candidate must serve at least one underserved outcome lives at the tool
layer, where the opportunity scores are available.\
""",
                "properties": {
                    "created_at": {"format": "date-time", "title": "Created At", "type": "string"},
                    "evidence_ids": {
                        "description": "Evidence that supports the hypothesis",
                        "items": {"type": "string"},
                        "title": "Evidence Ids",
                        "type": "array",
                    },
                    "hypothesis": {
                        "description": "Why this solution would serve the linked outcomes",
                        "title": "Hypothesis",
                        "type": "string",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "outcome_ids": {
                        "description": "The underserved outcomes this candidate serves",
                        "items": {"type": "string"},
                        "title": "Outcome Ids",
                        "type": "array",
                    },
                    "status": {
                        "$ref": "#/$defs/CandidateStatus",
                        "default": "proposed",
                        "description": "Where the candidate is in its life",
                    },
                    "strategy_path": {
                        "anyOf": [{"$ref": "#/$defs/StrategyKind"}, {"type": "null"}],
                        "default": None,
                        "description": "The Stage 6 path this candidate bets on, when chosen",
                    },
                    "title": {
                        "description": "Short human label for the proposed solution",
                        "title": "Title",
                        "type": "string",
                    },
                },
                "required": ["hypothesis", "title"],
                "title": "CandidateSolution",
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
                    "quote_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The Evidence record this outcome was promoted from",
                        "title": "Quote Id",
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
            "DecisionRecord": {
                "description": """\
A recorded decision about a subject (typically an accepted outcome).

Persisted so the loop can be replayed: a decision names what was chosen and
why, and is the parent of the :class:`BetRecord` that tests it.\
""",
                "properties": {
                    "choice": {
                        "description": "What was chosen",
                        "title": "Choice",
                        "type": "string",
                    },
                    "decided_at": {
                        "description": "ISO-8601 timestamp of the decision",
                        "title": "Decided At",
                        "type": "string",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "rationale": {
                        "description": "Why it was chosen",
                        "title": "Rationale",
                        "type": "string",
                    },
                    "subject_id": {
                        "description": "The Outcome this decision is about",
                        "title": "Subject Id",
                        "type": "string",
                    },
                },
                "required": ["choice", "decided_at", "rationale", "subject_id"],
                "title": "DecisionRecord",
                "type": "object",
            },
            "Evidence": {
                "description": "A captured research record linked (optionally) to ODI artifacts.",
                "properties": {
                    "confidence": {
                        "default": "claimed",
                        "description": "Whether the record was confirmed by the person (verified) or asserted without confirmation (claimed)",
                        "enum": ["claimed", "verified"],
                        "title": "Confidence",
                        "type": "string",
                    },
                    "content": {
                        "description": "Normalized text content of the record",
                        "title": "Content",
                        "type": "string",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "impact": {
                        "default": "medium",
                        "description": "How much this evidence moves the outcome score; mirrors JPD's insights impact rating",
                        "enum": ["high", "low", "medium"],
                        "title": "Impact",
                        "type": "string",
                    },
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
                    "origin": {
                        "default": "user",
                        "description": "Where this row came from",
                        "enum": ["demo", "imported", "sample", "user"],
                        "title": "Origin",
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
                        "description": "Connector kind, e.g. mcp, rest, webhook, manual — or demo for a fixture",
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
                    "url": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "External URL/link to the signal/evidence in the source system",
                        "title": "Url",
                    },
                },
                "required": ["content", "name", "source_kind", "source_name"],
                "title": "Evidence",
                "type": "object",
            },
            "ExtractedCandidate": {
                "$defs": {
                    "CandidateStatus": {
                        "description": "Where a candidate is in its life: proposed, accepted, rejected, or parked.",
                        "enum": ["accepted", "merged", "parked", "proposed", "rejected"],
                        "title": "CandidateStatus",
                        "type": "string",
                    }
                },
                "description": """\
A candidate the spine extractor proposed from a raw quote.

Distinct from :class:`OutcomeCandidate`, which belongs to an Interview quote
in the store: the spine's demo and tests hand over a quote string directly,
so this record carries the job and step it would attach to instead of a
required interview link.\
""",
                "properties": {
                    "confidence": {
                        "anyOf": [
                            {"maximum": 1.0, "minimum": 0.0, "type": "number"},
                            {"type": "null"},
                        ],
                        "default": None,
                        "description": "Extractor confidence, displayed not thresholded",
                        "title": "Confidence",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "interview_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The interview record, if known",
                        "title": "Interview Id",
                    },
                    "job_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The Job this candidate would become an outcome of",
                        "title": "Job Id",
                    },
                    "merged_into": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The existing Outcome a merge folded this candidate into",
                        "title": "Merged Into",
                    },
                    "outcome_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The Outcome an acceptance created, or a merge folded into",
                        "title": "Outcome Id",
                    },
                    "quote_id": {
                        "description": "The source quote this candidate came from",
                        "title": "Quote Id",
                        "type": "string",
                    },
                    "rationale": {
                        "default": "",
                        "description": "Why the extractor proposed it, or the validator's reason when rejected",
                        "title": "Rationale",
                        "type": "string",
                    },
                    "rejection_reason": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "Why a person rejected this candidate; required to reject",
                        "title": "Rejection Reason",
                    },
                    "statement": {
                        "description": "The proposed ODI desired-outcome statement",
                        "title": "Statement",
                        "type": "string",
                    },
                    "status": {
                        "$ref": "#/$defs/CandidateStatus",
                        "default": "proposed",
                        "description": "Where this candidate sits in review",
                    },
                    "step_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The Step this candidate would attach to",
                        "title": "Step Id",
                    },
                },
                "required": ["quote_id", "statement"],
                "title": "ExtractedCandidate",
                "type": "object",
            },
            "Interview": {
                "description": """\
A research conversation: who took part, when, and the job it informs.

``participant_label`` is a free-text label, never a real name, email, or
company. The quote rows are the unit of work; there is no raw-transcript
field, because a filesystem/BLOB store would be a second record of truth.\
""",
                "properties": {
                    "conducted_at": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "ISO-8601 date/time the interview was conducted",
                        "title": "Conducted At",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "job_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The Job this interview informs",
                        "title": "Job Id",
                    },
                    "notes": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "Researcher notes about the interview",
                        "title": "Notes",
                    },
                    "participant_label": {
                        "description": "Free-text label such as 'Ana' or 'Participant 3', never a real name",
                        "title": "Participant Label",
                        "type": "string",
                    },
                    "participant_role": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The participant's role, if known",
                        "title": "Participant Role",
                    },
                    "source_kind": {
                        "default": "manual",
                        "description": "Where the transcript came from, e.g. manual",
                        "title": "Source Kind",
                        "type": "string",
                    },
                    "title": {
                        "description": "Short human-readable title for the interview",
                        "title": "Title",
                        "type": "string",
                    },
                },
                "required": ["participant_label", "title"],
                "title": "Interview",
                "type": "object",
            },
            "InterviewQuote": {
                "description": "One verbatim sentence from an interview, in service-assigned order.",
                "properties": {
                    "end_ms": {
                        "anyOf": [{"minimum": 0, "type": "integer"}, {"type": "null"}],
                        "default": None,
                        "description": "End offset in milliseconds",
                        "title": "End Ms",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "interview_id": {
                        "description": "The Interview this quote belongs to",
                        "title": "Interview Id",
                        "type": "string",
                    },
                    "ordinal": {
                        "description": "Service-assigned order within the interview",
                        "minimum": 0,
                        "title": "Ordinal",
                        "type": "integer",
                    },
                    "speaker": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "Who said it, if the transcript names them",
                        "title": "Speaker",
                    },
                    "start_ms": {
                        "anyOf": [{"minimum": 0, "type": "integer"}, {"type": "null"}],
                        "default": None,
                        "description": "Start offset in milliseconds",
                        "title": "Start Ms",
                    },
                    "text": {
                        "description": "The verbatim quote text",
                        "title": "Text",
                        "type": "string",
                    },
                },
                "required": ["interview_id", "ordinal", "text"],
                "title": "InterviewQuote",
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
                        "description": "Where this row came from",
                        "enum": ["demo", "imported", "sample", "user"],
                        "title": "Origin",
                        "type": "string",
                    },
                },
                "required": ["name"],
                "title": "Job",
                "type": "object",
            },
            "Link": {
                "$defs": {
                    "EntityType": {
                        "description": """\
The kinds of ODI entity a link can point at.

Closed on purpose: an open string lets one writer say ``serves`` and
another ``implements`` for the same meaning, and the graph stops being
queryable. There is no ``candidate`` member — no such model exists.\
""",
                        "enum": ["evidence", "job", "outcome", "segment", "step", "strategy"],
                        "title": "EntityType",
                        "type": "string",
                    },
                    "ExternalSystem": {
                        "description": "A system outside Agentic ODI that a link can point at.",
                        "enum": ["github", "jira", "jpd", "linear", "notion"],
                        "title": "ExternalSystem",
                        "type": "string",
                    },
                    "RelationshipType": {
                        "description": """\
The closed vocabulary of typed edges between two ODI entities.

Five values, no more. An external target (a Jira ticket, a Linear issue)
is ``relates_to`` plus ``external_system`` and ``external_id``, not a
relationship value of its own.\
""",
                        "enum": [
                            "blocked_by",
                            "duplicates",
                            "evidence_for",
                            "outcome_of",
                            "relates_to",
                        ],
                        "title": "RelationshipType",
                        "type": "string",
                    },
                },
                "description": """\
A first-class typed edge between two ODI entities.

A link says "this evidence supports that outcome" or "this outcome is a
step of that job" as structured data a query can answer, instead of prose
a reader has to interpret. A human approves each link before it is
written; this model owns only the invariants it can check alone.\
""",
                "properties": {
                    "created_at": {
                        "description": "When the link was created",
                        "format": "date-time",
                        "title": "Created At",
                        "type": "string",
                    },
                    "external_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "Target ID inside that external system",
                        "title": "External Id",
                    },
                    "external_system": {
                        "anyOf": [{"$ref": "#/$defs/ExternalSystem"}, {"type": "null"}],
                        "default": None,
                        "description": "External system the target lives in, if any",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "preview": {
                        "anyOf": [
                            {"additionalProperties": True, "type": "object"},
                            {"type": "null"},
                        ],
                        "default": None,
                        "description": "Cached preview of the target entity",
                        "title": "Preview",
                    },
                    "relationship_type": {
                        "$ref": "#/$defs/RelationshipType",
                        "description": "The type of relationship",
                    },
                    "source_id": {
                        "description": "The ID of the source entity",
                        "title": "Source Id",
                        "type": "string",
                    },
                    "source_type": {
                        "$ref": "#/$defs/EntityType",
                        "description": "The type of the source entity",
                    },
                    "target_id": {
                        "description": "The ID of the target entity",
                        "title": "Target Id",
                        "type": "string",
                    },
                    "target_type": {
                        "$ref": "#/$defs/EntityType",
                        "description": "The type of the target entity",
                    },
                },
                "required": [
                    "relationship_type",
                    "source_id",
                    "source_type",
                    "target_id",
                    "target_type",
                ],
                "title": "Link",
                "type": "object",
            },
            "MeasurementRecord": {
                "description": """\
What a bet measured, against its baseline.

``value`` may be ``None``: a measurement that has not been taken is
representable without inventing a number.\
""",
                "properties": {
                    "bet_id": {
                        "description": "The Bet this measurement belongs to",
                        "title": "Bet Id",
                        "type": "string",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "metric": {
                        "description": "The metric that was measured",
                        "title": "Metric",
                        "type": "string",
                    },
                    "observed_at": {
                        "description": "ISO-8601 timestamp of the observation",
                        "title": "Observed At",
                        "type": "string",
                    },
                    "value": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                        "description": "The measured value, if taken",
                        "title": "Value",
                    },
                },
                "required": ["bet_id", "metric", "observed_at"],
                "title": "MeasurementRecord",
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
                                "enum": ["measure", "method"],
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
                    "importance_n": {
                        "anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}],
                        "default": None,
                        "description": "People behind the importance score, when known",
                        "title": "Importance N",
                    },
                    "interval_computed_at": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "When the band was computed, for staleness (B3.2)",
                        "title": "Interval Computed At",
                    },
                    "interval_confidence_level": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                        "description": "Confidence level of the band, e.g. 0.95 (B3)",
                        "title": "Interval Confidence Level",
                    },
                    "interval_n": {
                        "anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}],
                        "default": None,
                        "description": "Observations the band was computed from (B3)",
                        "title": "Interval N",
                    },
                    "interval_seed": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "default": None,
                        "description": "Seed that reproduces the band (B3)",
                        "title": "Interval Seed",
                    },
                    "job_id": {
                        "description": "The ID of the Job this outcome relates to",
                        "title": "Job Id",
                        "type": "string",
                    },
                    "opportunity_high": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                        "description": "High end of the score band, when a band was computed (B3)",
                        "title": "Opportunity High",
                    },
                    "opportunity_low": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                        "description": "Low end of the score band, when a band was computed (B3)",
                        "title": "Opportunity Low",
                    },
                    "opportunity_score": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                        "description": "Opportunity score (Importance + max(Importance - Satisfaction, 0))",
                        "title": "Opportunity Score",
                    },
                    "origin": {
                        "default": "user",
                        "description": "Where this row came from",
                        "enum": ["demo", "imported", "sample", "user"],
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
                    "satisfaction_n": {
                        "anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}],
                        "default": None,
                        "description": "People behind the satisfaction score, when known",
                        "title": "Satisfaction N",
                    },
                    "score_method": {
                        "default": "estimate",
                        "description": "How the score was obtained: a one-person estimate, a survey, or an import",
                        "enum": ["estimate", "import", "survey"],
                        "title": "Score Method",
                        "type": "string",
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
                    "study_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
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
                        "enum": ["measure", "method"],
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
            "OutcomeCandidate": {
                "$defs": {
                    "CandidateStatus": {
                        "description": "Where a candidate is in its life: proposed, accepted, rejected, or parked.",
                        "enum": ["accepted", "merged", "parked", "proposed", "rejected"],
                        "title": "CandidateStatus",
                        "type": "string",
                    }
                },
                "description": """\
A desired-outcome statement proposed from one interview quote.

A candidate is not an :class:`Outcome`; it carries the evidence and the
decision until a person accepts it. ``status`` is the whole state machine,
and ``outcome_id`` records what acceptance produced so a retry cannot make
a second outcome.\
""",
                "properties": {
                    "confidence": {
                        "maximum": 1.0,
                        "minimum": 0.0,
                        "description": "Extractor confidence, 0 to 1",
                        "title": "Confidence",
                        "type": "number",
                    },
                    "decision_reason": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The reviewer's reason, required when rejected",
                        "title": "Decision Reason",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "interview_id": {
                        "description": "The Interview the quote belongs to",
                        "title": "Interview Id",
                        "type": "string",
                    },
                    "merged_into": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The candidate or outcome this was merged into, once merged",
                        "title": "Merged Into",
                    },
                    "outcome_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The Outcome acceptance produced, once accepted",
                        "title": "Outcome Id",
                    },
                    "quote_id": {
                        "description": "The verbatim quote this candidate came from",
                        "title": "Quote Id",
                        "type": "string",
                    },
                    "rationale": {
                        "default": "",
                        "description": "Why the extractor proposed it, or why a validator refused it",
                        "title": "Rationale",
                        "type": "string",
                    },
                    "statement": {
                        "description": "The proposed desired-outcome statement",
                        "title": "Statement",
                        "type": "string",
                    },
                    "status": {
                        "$ref": "#/$defs/CandidateStatus",
                        "default": "proposed",
                        "description": "Review state",
                    },
                },
                "required": ["confidence", "interview_id", "quote_id", "statement"],
                "title": "OutcomeCandidate",
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
                        "title": "ScheduledWorkStatus",
                        "type": "string",
                    },
                    "ScheduledWorkTriggerType": {
                        "enum": ["cron", "interval", "oneshot"],
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
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "Associated ODI Job ID, if any",
                        "title": "Job Id",
                    },
                    "last_run_at": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
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
                        "anyOf": [{"type": "null"}, {"type": "string"}],
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
                        "anyOf": [{"type": "null"}, {"type": "string"}],
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
            "ScoreSnapshot": {
                "description": """\
One accepted score state, kept so "did it move?" is a subtraction.

A snapshot records the score *and* its sample/method companions, because a
history of bare numbers cannot answer "did the evidence change or the
estimate?". It is written by one helper on every score-mutating path and
lives in the append-only event log, so replay reproduces it.

A snapshot is only written for an *accepted* mutation; a validation failure
creates neither a score change nor a snapshot.

The writer appends on every accepted ``update_outcome``, so a metadata-only
edit (method/count) and an equal-value re-submission each add a snapshot.
That is deliberate: the trail records that the decision was re-affirmed or
re-evidenced, and it keeps the count/method-only evidence state visible
rather than collapsing two unlike states into one identical number.\
""",
                "properties": {
                    "at": {
                        "description": "ISO-8601 UTC timestamp of the accepted mutation",
                        "title": "At",
                        "type": "string",
                    },
                    "id": {"title": "Id", "type": "string"},
                    "importance": {
                        "anyOf": [
                            {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                            {"type": "null"},
                        ],
                        "default": None,
                        "title": "Importance",
                    },
                    "importance_n": {
                        "anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}],
                        "default": None,
                        "title": "Importance N",
                    },
                    "method": {
                        "default": "estimate",
                        "enum": ["estimate", "import", "survey"],
                        "title": "Method",
                        "type": "string",
                    },
                    "note": {
                        "anyOf": [{"maxLength": 500, "type": "string"}, {"type": "null"}],
                        "default": None,
                        "description": "Why the number was given, when the caller recorded one",
                        "title": "Note",
                    },
                    "opportunity_score": {
                        "anyOf": [{"type": "null"}, {"type": "number"}],
                        "default": None,
                        "title": "Opportunity Score",
                    },
                    "outcome_id": {
                        "description": "The outcome this snapshot belongs to",
                        "title": "Outcome Id",
                        "type": "string",
                    },
                    "satisfaction": {
                        "anyOf": [
                            {"maximum": 10.0, "minimum": 1.0, "type": "number"},
                            {"type": "null"},
                        ],
                        "default": None,
                        "title": "Satisfaction",
                    },
                    "satisfaction_n": {
                        "anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}],
                        "default": None,
                        "title": "Satisfaction N",
                    },
                },
                "required": ["outcome_id"],
                "title": "ScoreSnapshot",
                "type": "object",
            },
            "Segment": {
                "$defs": {
                    "SegmentVerdict": {
                        "description": "Stage 5's verdict on a group of people, computed from their outcomes.",
                        "enum": ["appropriately_served", "overserved", "underserved"],
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
                    "computed_at_event_id": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "default": None,
                        "description": "The store revision this segment was derived from. None when it was derived before the field existed, which reads as unknown, not fresh.",
                        "title": "Computed At Event Id",
                    },
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
                        "anyOf": [{"type": "null"}, {"type": "string"}],
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
                    "stale": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "default": None,
                        "description": "Computed at read time, never stored: whether the store has moved on since computed_at_event_id. None when no read has labelled it yet.",
                        "title": "Stale",
                    },
                    "verdict": {
                        "anyOf": [{"$ref": "#/$defs/SegmentVerdict"}, {"type": "null"}],
                        "default": None,
                        "description": "Derived from the outcomes; None means not enough signal",
                    },
                },
                "required": ["confidence", "job_statement", "name", "people", "rationale"],
                "title": "Segment",
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
                    "origin": {
                        "default": "user",
                        "description": "Where this row came from",
                        "enum": ["demo", "imported", "sample", "user"],
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
                    "computed_at_event_id": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "default": None,
                        "description": "The store revision this strategy was derived from. None when it was derived before the field existed, which reads as unknown, not fresh.",
                        "title": "Computed At Event Id",
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
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "The segment this bet is aimed at",
                        "title": "Segment Id",
                    },
                    "stale": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "default": None,
                        "description": "Computed at read time, never stored: whether the store has moved on since computed_at_event_id. None when no read has labelled it yet.",
                        "title": "Stale",
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
                        "enum": ["closed", "fielding", "planned"],
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
                        "anyOf": [{"type": "null"}, {"type": "string"}],
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
            "SurveyInputSet": {
                "description": """\
The accepted paired survey inputs a band can be reproduced from (B3.1).

Persisted in the append-only event log so a stored band is reproducible
after a reload, not only for the process that imported it. Each entry is the
paired ``(importance, satisfaction)`` a respondent gave, in the canonical
order the import accepted them, plus a de-identified ``respondent_ref``.

No personal identifier is stored: ``respondent_ref`` is a caller-supplied
opaque token (the import's respondent id or a row label), never a name or an
email, and it is kept only so a repeated respondent stays one person under
the retention policy. It is not a public aggregate payload.

``input_ref`` is the versioned reference the interval slice records: it is
derived from the inputs so a band can name the exact set it came from, and it
changes when the set changes. ``study_id``/``wave`` are the lineage links the
retention decision must define; both are optional here because the policy is
not yet approved, so a missing link stays ``None`` rather than a guessed
study.\
""",
                "properties": {
                    "id": {"title": "Id", "type": "string"},
                    "input_ref": {
                        "description": "Versioned reference to this exact input set (B3.1)",
                        "title": "Input Ref",
                        "type": "string",
                    },
                    "job_id": {
                        "description": "The owning job, so a cross-job link is detectable",
                        "title": "Job Id",
                        "type": "string",
                    },
                    "method": {
                        "default": "survey",
                        "description": "How the inputs were obtained",
                        "title": "Method",
                        "type": "string",
                    },
                    "outcome_id": {
                        "description": "The outcome these paired inputs belong to",
                        "title": "Outcome Id",
                        "type": "string",
                    },
                    "pairs": {
                        "description": "Accepted (importance, satisfaction) pairs in canonical import order",
                        "items": {
                            "maxItems": 2,
                            "minItems": 2,
                            "prefixItems": [{"type": "number"}, {"type": "number"}],
                            "type": "array",
                        },
                        "title": "Pairs",
                        "type": "array",
                    },
                    "respondent_refs": {
                        "description": "De-identified per-pair respondent tokens, kept only to de-duplicate",
                        "items": {"type": "string"},
                        "title": "Respondent Refs",
                        "type": "array",
                    },
                    "study_id": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "Study lineage, when the policy defines it",
                        "title": "Study Id",
                    },
                    "wave": {
                        "anyOf": [{"type": "null"}, {"type": "string"}],
                        "default": None,
                        "description": "Study wave lineage, when the policy defines it",
                        "title": "Wave",
                    },
                },
                "required": ["input_ref", "job_id", "outcome_id"],
                "title": "SurveyInputSet",
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
