"""Tier 0 deterministic responder: branch routing, context, and the no-fabrication contract."""

from __future__ import annotations

import pytest
from agentic_odi_core.models import compute_opportunity_score
from agentic_odi_core.steve_jobs import (
    format_opportunity_score_insight,
    generate_steve_jobs_response,
)

# Representative keyword per branch, the header each branch must open with, and
# the surface it must point the person at. Order is the routing precedence.
_BRANCHES = [
    ("how does this process work", "### ODI, stage by stage", "/capture"),
    ("simulate the bet", "### Simulate the bet by hand", "/impact"),
    ("show me the evidence from the call", "### Evidence needs a source", "/capture"),
    ("calculate my score", "### Opportunity score", "compute_opportunity"),
]


@pytest.mark.parametrize("prompt,header,surface", _BRANCHES)
def test_keyword_routes_to_its_branch(prompt: str, header: str, surface: str) -> None:
    response = generate_steve_jobs_response(prompt)

    assert response.startswith(header)
    assert surface in response


@pytest.mark.parametrize("prompt,header,_surface", _BRANCHES)
def test_routing_is_case_insensitive_and_ignores_surrounding_space(
    prompt: str, header: str, _surface: str
) -> None:
    """Routing lowercases and strips the input before matching keywords."""
    noisy = f"   {prompt.upper()}   "

    assert generate_steve_jobs_response(noisy).startswith(header)


def test_guidelines_branch_wins_over_score_branch() -> None:
    """Branches are checked in a fixed order; the first family match wins.

    A prompt naming both a stage and a score must land on the stage guide, so
    the answer to "how does this work" is never a refusal to compute a number.
    """
    response = generate_steve_jobs_response("which stage do I calculate a score in?")

    assert response.startswith("### ODI, stage by stage")
    assert "compute_opportunity" not in response


def test_unknown_intent_falls_through_to_the_deterministic_default() -> None:
    response = generate_steve_jobs_response("hello there")

    assert response.startswith('I received your intent: **"hello there"**.')
    assert "deterministic" in response
    # The hand-run surfaces are listed so the person is never left at a dead end.
    for command in ("/start", "/capture", "/jobmap", "/landscape", "/help"):
        assert command in response


def test_default_branch_echoes_the_stripped_intent() -> None:
    """The echoed intent is trimmed, so stray whitespace never reaches the reply."""
    response = generate_steve_jobs_response("   plan my study   ")

    assert '**"plan my study"**' in response
    assert '**"   plan my study   "**' not in response


@pytest.mark.parametrize("prompt,_header,_surface", _BRANCHES)
def test_working_context_is_appended_to_every_branch(
    prompt: str, _header: str, _surface: str
) -> None:
    """Context is a suffix on every branch, not only the default one."""
    response = generate_steve_jobs_response(
        prompt, context={"product_name": "Acme", "job_statement": "pass on lessons"}
    )

    assert response.endswith("**Working context:** **Acme** — pass on lessons")


def test_working_context_renders_each_field_it_receives() -> None:
    product_only = generate_steve_jobs_response("hi", context={"product_name": "Acme"})
    assert "**Working context:** **Acme**" in product_only

    job_only = generate_steve_jobs_response("hi", context={"job_statement": "pass on lessons"})
    assert "**Working context:** pass on lessons" in job_only


@pytest.mark.parametrize("context", [None, {}])
def test_absent_or_empty_context_adds_no_context_block(context: dict[str, str] | None) -> None:
    response = generate_steve_jobs_response("hi", context=context)

    assert "Working context" not in response


def test_empty_context_values_do_not_add_a_context_block() -> None:
    """Falsy field values are skipped rather than rendered as an empty block."""
    response = generate_steve_jobs_response("hi", context={"product_name": "", "job_statement": ""})

    assert "Working context" not in response


def test_default_branch_never_fabricates_scores_or_customer_data() -> None:
    """Tier 0's honesty contract: no invented scores, quotes, or customer names."""
    response = generate_steve_jobs_response("hello")

    assert "Score:" not in response
    assert "Importance:" not in response
    assert "3,000 hours" not in response


def test_score_branch_points_at_compute_opportunity_instead_of_computing() -> None:
    """A score request is redirected to the tool, never answered with a number."""
    response = generate_steve_jobs_response("calculate score 9.0 3.0")

    assert "compute_opportunity(importance, satisfaction)" in response
    # 9 + max(9 - 3, 0) = 15; the responder must not print it.
    assert "15" not in response
    assert "Breakthrough Opportunity" not in response


@pytest.mark.parametrize(
    "importance,satisfaction,verdict",
    [
        (9.0, 3.0, "underserved"),  # 15.0 > 10
        (10.0, 9.0, "underserved"),  # 11.0 > 10
        (10.0, 10.0, "appropriately served"),  # exactly 10.0
        (5.0, 8.0, "overserved"),  # 5.0 < 10, satisfaction exceeds importance
    ],
)
def test_deprecated_formatter_labels_the_verdict_at_its_boundaries(
    importance: float, satisfaction: float, verdict: str
) -> None:
    insight = format_opportunity_score_insight(importance, satisfaction)

    assert insight.endswith(f"→ {verdict}")


def test_deprecated_formatter_reports_core_score_and_inputs() -> None:
    """The formatter's score agrees with the canonical ODI calculation."""
    importance, satisfaction = 7.0, 2.0
    expected = compute_opportunity_score(importance, satisfaction)

    insight = format_opportunity_score_insight(importance, satisfaction)

    assert f"Score: {expected:.2f}" in insight
    assert f"Importance: {importance:.1f}/10" in insight
    assert f"Satisfaction: {satisfaction:.1f}/10" in insight


def test_deprecated_formatter_quotes_the_statement_when_given() -> None:
    with_statement = format_opportunity_score_insight(9.0, 3.0, statement="cut the wait")
    without_statement = format_opportunity_score_insight(9.0, 3.0)

    assert with_statement.startswith('Outcome: "cut the wait"')
    assert without_statement.startswith("Opportunity Score Calculation")
