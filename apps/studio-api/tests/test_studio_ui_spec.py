"""Tests for the catalog-driven UI validator."""

from __future__ import annotations

from typing import Any

from agentic_odi_studio_api.studio.ui_spec import MAX_DEPTH, UiCatalog

ACTIONS: dict[str, Any] = {
    "type": "array",
    "maxItems": 40,
    "items": {
        "type": "object",
        "required": ["label", "intent"],
        "properties": {
            "label": {"type": "string"},
            "intent": {"type": "string"},
            "tone": {"enum": ["primary", "ghost"]},
        },
    },
}

STAGES = [
    "define",
    "locate",
    "prepare",
    "confirm",
    "execute",
    "monitor",
    "modify",
    "conclude",
]

DEMO_CATALOG: dict[str, Any] = {
    "version": 1,
    "components": [
        {
            "type": "job-map",
            "kind": "leaf",
            "description": "The eight universal job stages for one job.",
            "acceptsChildren": False,
            "props": {
                "type": "object",
                "required": ["job", "steps"],
                "properties": {
                    "job": {"type": "string"},
                    "steps": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 8,
                        "items": {
                            "type": "object",
                            "required": ["name"],
                            "properties": {
                                "name": {"type": "string"},
                                "stage": {"enum": STAGES},
                                "note": {"type": "string"},
                            },
                        },
                    },
                    "actions": ACTIONS,
                },
            },
        },
        {
            "type": "opportunity-board",
            "kind": "leaf",
            "description": "A ranked table of outcomes by opportunity score.",
            "acceptsChildren": False,
            "props": {
                "type": "object",
                "required": ["outcomes"],
                "properties": {
                    "title": {"type": "string"},
                    "outcomes": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 12,
                        "items": {
                            "type": "object",
                            "required": ["id", "statement", "importance", "satisfaction"],
                            "properties": {
                                "id": {"type": "string"},
                                "statement": {"type": "string"},
                                "importance": {"type": "number", "minimum": 0, "maximum": 10},
                                "satisfaction": {"type": "number", "minimum": 0, "maximum": 10},
                            },
                        },
                    },
                    "actions": ACTIONS,
                },
            },
        },
        {
            "type": "impact-simulation",
            "kind": "leaf",
            "description": "A before/after simulation of a proposed bet.",
            "acceptsChildren": False,
            "props": {
                "type": "object",
                "required": ["outcome", "bet", "before", "after"],
                "properties": {
                    "outcome": {
                        "type": "object",
                        "required": ["id", "statement"],
                        "properties": {
                            "id": {"type": "string"},
                            "statement": {"type": "string"},
                        },
                    },
                    "bet": {"type": "string"},
                    "before": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "after": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "metrics": {
                        "type": "array",
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "required": ["label", "value"],
                            "properties": {
                                "label": {"type": "string"},
                                "value": {"type": "string"},
                                "delta": {"type": "string"},
                            },
                        },
                    },
                    "verdict": {"type": "string"},
                    "actions": ACTIONS,
                },
            },
        },
        {
            "type": "evidence-quote",
            "kind": "leaf",
            "description": "A verbatim customer signal with its lineage.",
            "acceptsChildren": False,
            "props": {
                "type": "object",
                "required": ["source", "quote"],
                "properties": {
                    "source": {"type": "string"},
                    "quote": {"type": "string"},
                    "linkedTo": {"type": "string"},
                    "severity": {"enum": ["low", "medium", "high", "critical"]},
                    "actions": ACTIONS,
                },
            },
        },
        {
            "type": "stack",
            "kind": "layout",
            "description": "Vertical or horizontal grouping of other nodes.",
            "acceptsChildren": True,
            "props": {
                "type": "object",
                "properties": {
                    "direction": {"enum": ["vertical", "horizontal"]},
                    "gap": {"enum": ["sm", "md", "lg"]},
                    "actions": ACTIONS,
                },
            },
        },
    ],
}


def _catalog() -> UiCatalog:
    catalog = UiCatalog.from_manifest(DEMO_CATALOG)
    assert catalog is not None
    return catalog


def _outcome(**overrides: Any) -> dict[str, Any]:
    props = {
        "id": "O-1",
        "statement": "Minimize the time it takes to propagate secrets",
        "importance": 9,
        "satisfaction": 3,
    }
    props.update(overrides)
    return {"type": "opportunity-board", "props": {"outcomes": [props]}}


# ---------------------------------------------------------------------------
# Manifest handling
# ---------------------------------------------------------------------------


def test_missing_manifest_yields_no_catalog() -> None:
    assert UiCatalog.from_manifest(None) is None
    assert UiCatalog.from_manifest({"version": 1, "components": []}) is None
    assert UiCatalog.from_manifest("not a manifest") is None


def test_catalog_keeps_component_order_and_drops_duplicates() -> None:
    catalog = UiCatalog.from_manifest(
        {
            "components": [
                {"type": "b", "props": {}},
                {"type": "a", "props": {}},
                {"type": "a", "props": {}},
                {"nope": True},
            ]
        }
    )

    assert catalog is not None
    assert catalog.types == ["b", "a"]


# ---------------------------------------------------------------------------
# Tool schema + description
# ---------------------------------------------------------------------------


def test_tool_schema_enumerates_the_renderable_types() -> None:
    schema = _catalog().tool_schema()

    assert schema["required"] == ["type"]
    assert schema["properties"]["type"]["enum"] == _catalog().types


def test_description_marks_required_props_and_children() -> None:
    description = _catalog().describe()

    assert "- job-map(job*, steps*) —" in description
    assert "Children allowed." in description
    assert "Optional actions." in description
    assert "actions*" not in description


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_accepts_a_valid_surface() -> None:
    assert _catalog().validate(_outcome()) is None


def test_accepts_nested_layout_children() -> None:
    job_map = {
        "type": "job-map",
        "props": {"job": "Ship it", "steps": [{"name": "Define"}]},
    }
    spec = {"type": "stack", "props": {"gap": "sm"}, "children": [_outcome(), job_map]}
    assert _catalog().validate(spec) is None


def test_rejects_an_unknown_type_and_lists_the_alternatives() -> None:
    problem = _catalog().validate({"type": "salesforce-dashboard", "props": {}})

    assert problem is not None
    assert "not a renderable type" in problem
    assert "job-map" in problem


def test_rejects_a_missing_required_prop() -> None:
    problem = _catalog().validate({"type": "job-map", "props": {"job": "Ship it"}})

    assert problem == "`job-map.props.steps` is required"


def test_rejects_a_score_outside_the_band() -> None:
    problem = _catalog().validate(_outcome(importance=11))

    assert problem is not None
    assert "importance" in problem
    assert "at most 10" in problem


def test_tolerates_an_unknown_enum_on_an_optional_field() -> None:
    # Same policy as the renderer: an optional prop with a bad value is dropped.
    spec = {
        "type": "job-map",
        "props": {"job": "Ship it", "steps": [{"name": "Define", "stage": "vibes"}]},
    }

    assert _catalog().validate(spec) is None


def test_rejects_a_missing_required_field_inside_a_required_object() -> None:
    spec = {
        "type": "impact-simulation",
        "props": {
            "outcome": {"id": "O-1"},
            "bet": "A daemon",
            "before": ["45 minutes"],
            "after": ["30 seconds"],
        },
    }

    problem = _catalog().validate(spec)

    assert problem is not None
    assert problem == "`impact-simulation.props.outcome.statement` is required"


def test_tolerates_a_bad_optional_array_item() -> None:
    spec = {
        "type": "impact-simulation",
        "props": {
            "outcome": {"id": "O-1", "statement": "Minimize time"},
            "bet": "A daemon",
            "before": ["45 minutes"],
            "after": ["30 seconds"],
            "metrics": [{"label": "Time to value"}],
        },
    }

    assert _catalog().validate(spec) is None


def test_rejects_a_non_numeric_score() -> None:
    problem = _catalog().validate(_outcome(importance="nine"))

    assert problem is not None
    assert "must be a number" in problem


def test_strips_unknown_props_instead_of_failing() -> None:
    spec = _outcome()
    spec["props"]["outcomes"][0]["dangerouslySetInnerHTML"] = "<script/>"
    spec["props"]["outcomes"][0]["tone"] = "shout"

    assert _catalog().validate(spec) is None


def test_tolerates_stray_children_on_a_leaf() -> None:
    spec = {**_outcome(), "children": [{"type": "job-map", "props": {}}]}

    assert _catalog().validate(spec) is None


def test_rejects_a_tree_deeper_than_the_limit() -> None:
    spec: dict[str, Any] = {"type": "job-map", "props": {"job": "x", "steps": [{"name": "y"}]}}
    for _ in range(MAX_DEPTH + 1):
        spec = {"type": "stack", "props": {}, "children": [spec]}

    problem = _catalog().validate(spec)

    assert problem is not None
    assert "deeper than" in problem


def test_rejects_a_surface_that_is_not_an_object() -> None:
    assert _catalog().validate("just text") == "a UI node must be an object"
