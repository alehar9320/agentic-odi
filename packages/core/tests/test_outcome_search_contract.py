"""ALH-194 — search_outcomes is a read on the contract surface, like the list reads."""

from __future__ import annotations

from agentic_odi_core.contract import TOOL_SPECS, ToolEffect, ToolName

FIELDS = (
    "text",
    "stage",
    "theme_ids",
    "confidence",
    "tags",
    "min_score",
    "max_score",
    "job_id",
    "sort",
    #: A theme can stand for the themes under it, and that is a property of the query, not of
    #: the page — so it sits with the fields beside ``sort`` rather than with the paging below.
    "include_children",
)


def test_search_outcomes_is_named_in_the_contract() -> None:
    assert ToolName.SEARCH_OUTCOMES.value == "search_outcomes"
    assert "search_outcomes" in TOOL_SPECS


def test_search_outcomes_declares_the_query_fields_plus_a_page() -> None:
    spec = TOOL_SPECS[ToolName.SEARCH_OUTCOMES.value]

    assert spec.arguments == FIELDS + ("limit", "offset")
    assert spec.required == ()


def test_search_outcomes_is_a_read_even_though_its_name_is_not_a_get_or_list() -> None:
    spec = TOOL_SPECS[ToolName.SEARCH_OUTCOMES.value]

    #: _derive_effect would call a search_ verb a write; a search that writes
    #: nothing must say so explicitly, the way evaluate_outcome already does.
    assert spec.effect is ToolEffect.READ
