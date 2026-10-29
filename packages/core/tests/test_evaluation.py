"""The outcome format guard: what it accepts, and what it refuses to bless."""

from __future__ import annotations

from agentic_odi_core.evaluation import evaluate_outcome_statement

WELL_FORMED = "Minimize the time it takes to onboard a customer when they sign up"


def test_a_well_formed_statement_passes_clean() -> None:
    result = evaluate_outcome_statement(WELL_FORMED)

    assert result["valid"] is True
    assert result["direction"] == "minimize"
    assert result["issues"] == []
    assert result["suggestions"] == []


def test_a_maximize_statement_passes_and_reports_its_direction() -> None:
    result = evaluate_outcome_statement(
        "Maximize the share of customers reaching first value when onboarding"
    )

    assert result["valid"] is True
    assert result["direction"] == "maximize"


def test_a_solution_framed_statement_is_flagged() -> None:
    result = evaluate_outcome_statement("I want a notification")

    assert result["valid"] is False
    assert result["direction"] is None
    issues = " ".join(result["issues"])
    assert "Minimize" in issues
    assert "context" in issues.lower()
    assert result["suggestions"]


def test_a_vague_statement_is_flagged_with_the_term_to_replace() -> None:
    result = evaluate_outcome_statement("Make it faster")

    assert result["valid"] is False
    issues = " ".join(result["issues"])
    assert "Minimize" in issues
    assert "faster" in issues
    assert "too short" in issues


def test_a_statement_without_its_context_is_flagged() -> None:
    # "Minimize the time to X" names a direction and an object but never says
    # when, so it cannot be measured against a situation.
    result = evaluate_outcome_statement("Minimize the time to deploy")

    assert result["valid"] is False
    assert any("context" in issue.lower() for issue in result["issues"])


def test_a_statement_over_two_hundred_characters_is_flagged() -> None:
    result = evaluate_outcome_statement(
        "Minimize the total elapsed time from a customer asking a question "
        "to a support engineer closing the loop while the account is in its "
        "first ninety days and the request spans more than one timezone while "
        "the team works across two continents"
    )

    assert result["valid"] is False
    assert any("200 characters" in issue for issue in result["issues"])


def test_the_statement_is_echoed_without_surrounding_space() -> None:
    result = evaluate_outcome_statement(f"  {WELL_FORMED}  ")

    assert result["statement"] == WELL_FORMED


def test_every_issue_comes_with_a_way_to_fix_it() -> None:
    result = evaluate_outcome_statement("Make it faster")

    assert len(result["suggestions"]) == len(result["issues"])


def test_a_missing_direction_is_reported() -> None:
    result = evaluate_outcome_statement("The time to onboard a customer when they sign up")

    assert result["valid"] is False
    assert result["direction"] is None
    assert any("'Minimize' or 'Maximize'" in issue for issue in result["issues"])


def test_a_missing_object_of_control_is_reported() -> None:
    result = evaluate_outcome_statement("Minimize onboarding time when a customer signs up")

    assert result["valid"] is False
    assert any("after 'the'" in issue for issue in result["issues"])


def test_a_short_statement_is_reported() -> None:
    result = evaluate_outcome_statement("Minimize the time")

    assert result["valid"] is False
    assert any("too short" in issue for issue in result["issues"])


def test_blank_input_reports_every_missing_part() -> None:
    result = evaluate_outcome_statement("   ")

    assert result["valid"] is False
    assert len(result["issues"]) == 5
    assert result["statement"] == ""
