"""Unit tests for the desired-outcome format check."""

from __future__ import annotations

from agentic_odi_core.evaluation import evaluate_outcome_statement

_VALID = "Minimize the time it takes to onboard a new customer when they sign up"


def test_a_well_formed_statement_is_valid() -> None:
    result = evaluate_outcome_statement(_VALID)

    assert result["valid"] is True
    assert result["direction"] == "minimize"
    assert result["issues"] == []
    assert result["suggestions"] == []
    assert result["statement"] == _VALID


def test_maximize_is_recognised_as_a_direction() -> None:
    result = evaluate_outcome_statement(
        "Maximize the number of accounts a rep closes while the quarter is open"
    )

    assert result["valid"] is True
    assert result["direction"] == "maximize"


def test_a_missing_direction_is_reported() -> None:
    result = evaluate_outcome_statement("The time to onboard a customer when they sign up")

    assert result["valid"] is False
    assert result["direction"] is None
    assert any("'Minimize' or 'Maximize'" in issue for issue in result["issues"])


def test_a_missing_object_of_control_is_reported() -> None:
    result = evaluate_outcome_statement("Minimize onboarding time when a customer signs up")

    assert result["valid"] is False
    assert any("after 'the'" in issue for issue in result["issues"])


def test_a_missing_context_marker_is_reported() -> None:
    result = evaluate_outcome_statement("Minimize the time it takes to onboard a customer")

    assert result["valid"] is False
    assert any("execution context" in issue for issue in result["issues"])


def test_a_short_statement_is_reported() -> None:
    result = evaluate_outcome_statement("Minimize the time")

    assert result["valid"] is False
    assert any("too short" in issue for issue in result["issues"])


def test_vague_terms_are_named() -> None:
    result = evaluate_outcome_statement(
        "Minimize the effort to onboard a customer when the team is moving faster"
    )

    assert result["valid"] is False
    assert any("faster" in issue and "vague" in issue for issue in result["issues"])


def test_a_statement_over_two_hundred_characters_is_reported() -> None:
    statement = (
        "Minimize the number of manual checks a support engineer repeats for every "
        "single account that moves through the renewal pipeline when the billing "
        "system has not yet received the updated contract terms from the legal team"
    )
    assert len(statement) > 200

    result = evaluate_outcome_statement(statement)

    assert result["valid"] is False
    assert any("200 characters" in issue for issue in result["issues"])


def test_blank_input_reports_every_missing_part() -> None:
    result = evaluate_outcome_statement("   ")

    assert result["valid"] is False
    assert len(result["issues"]) == 4
    assert result["statement"] == ""
