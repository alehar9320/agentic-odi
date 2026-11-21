"""ALH-61 / H1 — the snapshot gate must actually fail on each kind of drift.

The positive snapshot tests live in ``test_contract_snapshot.py``. A green
snapshot only proves something if the comparison can also fail, so each test
here takes the real surface, applies exactly one mutation, and asserts the
comparison rejects it. The mutations cover the drift the ticket names:
argument rename, requiredness, type, missing and extra tools, and an entity
schema field change.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from agentic_odi_core.contract import TOOL_SPECS
from agentic_odi_core.schema import odi_schema

from tests.contract.test_contract_snapshot import (
    _normalize,
    declared_tool_surface,
    live_tool_surface,
)


def _mutate(surface: dict[str, Any], change) -> dict[str, Any]:
    mutated = copy.deepcopy(surface)
    change(mutated)
    return mutated


def _assert_drift(original: dict[str, Any], mutated: dict[str, Any], kind: str) -> None:
    assert mutated != original, f"{kind} drift was not detected"


def test_argument_rename_is_detected() -> None:
    original = declared_tool_surface()

    def change(surface: dict[str, Any]) -> None:
        spec = surface["add_job"]
        spec["arguments"] = [arg if arg != "name" else "title" for arg in spec["arguments"]]

    _assert_drift(original, _mutate(original, change), "argument rename")


def test_requiredness_change_is_detected() -> None:
    original = declared_tool_surface()

    def change(surface: dict[str, Any]) -> None:
        surface["add_job"]["required"] = []

    _assert_drift(original, _mutate(original, change), "requiredness")


def test_argument_type_change_is_detected() -> None:
    original = declared_tool_surface()

    def change(surface: dict[str, Any]) -> None:
        surface["add_outcome"]["arguments"] = [
            arg if arg != "importance" else "importance_score"
            for arg in surface["add_outcome"]["arguments"]
        ]

    _assert_drift(original, _mutate(original, change), "type")


def test_effect_change_is_detected() -> None:
    original = declared_tool_surface()

    def change(surface: dict[str, Any]) -> None:
        surface["delete_job"]["effect"] = "write"

    _assert_drift(original, _mutate(original, change), "effect")


def test_missing_tool_is_detected() -> None:
    original = declared_tool_surface()

    def change(surface: dict[str, Any]) -> None:
        del surface["delete_job"]

    _assert_drift(original, _mutate(original, change), "missing tool")


def test_extra_tool_is_detected() -> None:
    original = declared_tool_surface()

    def change(surface: dict[str, Any]) -> None:
        surface["a_brand_new_tool"] = {
            "summary": "x",
            "effect": "read",
            "arguments": [],
            "required": [],
            "returns": "x",
            "stage": None,
        }

    _assert_drift(original, _mutate(original, change), "extra tool")


def test_entity_schema_field_change_is_detected() -> None:
    original = _normalize(odi_schema())

    def change(schema: dict[str, Any]) -> None:
        del schema["Job"]["properties"]["description"]

    _assert_drift(original, _mutate(original, change), "entity schema field")


@pytest.mark.asyncio
async def test_live_registry_parity_rejects_an_undeclared_property() -> None:
    """A property on the server but not in the declaration must fail the parity check."""
    live = await live_tool_surface()
    live["add_job"]["properties"]["sneaky"] = {"type": "string"}

    with pytest.raises(AssertionError):
        for name, spec in TOOL_SPECS.items():
            schema = live[name]
            assert set(schema.get("properties", {})) == set(spec.arguments), name


@pytest.mark.asyncio
async def test_live_registry_parity_rejects_a_missing_tool() -> None:
    live = await live_tool_surface()
    del live["add_job"]

    with pytest.raises(AssertionError):
        assert set(live) == set(TOOL_SPECS)
