"""Rendering: tables, blocks, JSON, truncation, and unicode safety."""

from __future__ import annotations

import json

from cli.render import (
    render_customer_outcome,
    render_customer_outcome_list,
    render_deleted,
    render_saved,
    render_score,
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
