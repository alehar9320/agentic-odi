"""Rendering: tables, blocks, JSON, truncation, and unicode safety."""

from __future__ import annotations

import json

from agentic_odi_cli.render import (
    render_customer_outcome,
    render_customer_outcome_list,
    render_deleted,
    render_saved,
    render_score,
    render_segment,
    render_segment_list,
    render_strategy,
)


def _outcome(**overrides) -> dict:
    outcome = {
        "id": "abc",
        "job_id": "job-1",
        "customer_value": {
            "statement": "Minimize the time to onboard",
            "importance": 8.8,
            "satisfaction": 3.2,
        },
        "business_value": {"category": "cost_reduction", "statement": "Saves hours"},
        "opportunity_score": 14.4,
    }
    outcome.update(overrides)
    return outcome


def test_list_empty_is_friendly():
    assert render_customer_outcome_list([], as_json=False) == "No customer outcomes found."


def test_list_empty_json_is_array():
    assert json.loads(render_customer_outcome_list([], as_json=True)) == []


def test_list_truncates_long_statements():
    long = "Minimize " + "x" * 200
    rendered = render_customer_outcome_list(
        [_outcome(customer_value={"statement": long, "importance": 1, "satisfaction": 1})],
        as_json=False,
    )
    assert "…" in rendered
    assert long not in rendered


def test_list_keeps_unicode_intact():
    rendered = render_customer_outcome_list(
        [
            _outcome(
                customer_value={
                    "statement": "Minimise the café queue",
                    "importance": 1,
                    "satisfaction": 1,
                }
            )
        ],
        as_json=False,
    )
    assert "café" in rendered


def test_outcome_block_formats_scores_to_two_decimals():
    rendered = render_customer_outcome(_outcome(), as_json=False)
    assert "14.40" in rendered
    assert "14.400000" not in rendered


def test_outcome_json_is_parseable():
    assert json.loads(render_customer_outcome(_outcome(), as_json=True))["id"] == "abc"


def test_non_dict_payloads_pass_through():
    assert render_customer_outcome("raw text", as_json=False) == "raw text"
    assert render_saved("created", "raw text", as_json=False) == "raw text"
    assert render_customer_outcome_list("raw text", as_json=False) == "raw text"


def test_deleted_json_and_human():
    assert json.loads(render_deleted("abc", as_json=True)) == {"id": "abc", "deleted": True}
    assert "abc" in render_deleted("abc", as_json=False)


def test_score_json_and_human():
    assert render_score(8, 2, 14.0, as_json=False) == "Opportunity score: 14.00"
    payload = json.loads(render_score(8, 2, 14.0, as_json=True))
    assert payload["opportunity_score"] == 14.0


def test_saved_dict_can_be_rendered_as_json():
    payload = json.loads(render_saved("created", _outcome(), as_json=True))

    assert payload["id"] == "abc"


def test_json_keeps_plain_strings_unchanged():
    assert render_customer_outcome("not json", as_json=True) == "not json"


def test_score_renderer_passes_through_non_numeric_values():
    outcome = _outcome(customer_value={"statement": "s", "importance": True, "satisfaction": "n/a"})

    rendered = render_customer_outcome(outcome, as_json=False)

    assert "True" in rendered
    assert "n/a" in rendered


def _segment(**overrides) -> dict:
    segment = {
        "id": "SEG-1",
        "job_id": "JOB-1",
        "name": "Platform engineers",
        "people": "Platform engineers",
        "job_statement": "Rotate a leaked secret",
        "verdict": "underserved",
        "confidence": 0.8,
        "outcome_ids": ["O-1", "O-2"],
        "rationale": "Two outcomes on the gather step.",
        "stale": False,
    }
    segment.update(overrides)
    return segment


def test_a_stale_segment_is_labelled_stale_in_the_list():
    rendered = render_segment_list([_segment(stale=True)], as_json=False)

    assert "stale" in rendered


def test_a_current_segment_is_labelled_current():
    rendered = render_segment_list([_segment(stale=False)], as_json=False)

    assert "current" in rendered


def test_a_segment_with_no_freshness_reads_as_unknown_not_current():
    """An older backend omits the flag; absence must not read as fresh."""
    rendered = render_segment_list([_segment(stale=None)], as_json=False)

    assert "unknown" in rendered


def test_a_segment_shows_its_freshness_when_read_alone():
    rendered = render_segment(_segment(stale=True), as_json=False)

    assert "stale" in rendered


def test_a_strategy_shows_its_freshness():
    strategy = {
        "id": "STR-1",
        "kind": "differentiated",
        "segment_id": "SEG-1",
        "thesis": "Match each line is underserved.",
        "bets": ["Build against match each line"],
        "rejected": [{"kind": "disruptive", "why": "no segment is overserved"}],
        "stale": True,
    }

    rendered = render_strategy(strategy, as_json=False)

    assert "stale" in rendered
