"""Tests for outcome-statement evaluation."""

from __future__ import annotations

from agentic_odi_core.evaluation import evaluate_outcome_statement


def test_valid_maximize_statement_passes() -> None:
    result = evaluate_outcome_statement(
        "Maximize the conversion rate when onboarding a new customer."
    )
    assert result["valid"] is True
    assert result["direction"] == "maximize"
    assert result["issues"] == []


def test_valid_minimize_statement_passes() -> None:
    result = evaluate_outcome_statement(
        "Minimize the time to resolve a support ticket before the customer churns."
    )
    assert result["valid"] is True
    assert result["direction"] == "minimize"
    assert result["issues"] == []


def test_missing_direction_reports_issue() -> None:
    result = evaluate_outcome_statement("The conversion rate when onboarding.")
    assert result["valid"] is False
    assert result["direction"] is None
    assert any("Minimize" in issue or "Maximize" in issue for issue in result["issues"])


def test_vague_term_reports_issue() -> None:
    result = evaluate_outcome_statement("Improve the onboarding flow when a user signs up.")
    assert result["valid"] is False
    assert any("improve" in issue.lower() for issue in result["issues"])


def test_too_short_statement_reports_issue() -> None:
    result = evaluate_outcome_statement("Maximize it.")
    assert result["valid"] is False
    assert any("too short" in issue for issue in result["issues"])


def test_overly_long_statement_reports_issue() -> None:
    long_statement = "Maximize " + ("the metric " * 40) + "when doing something."
    result = evaluate_outcome_statement(long_statement)
    assert result["valid"] is False
    assert any("200 characters" in issue for issue in result["issues"])


def test_missing_context_reports_issue() -> None:
    result = evaluate_outcome_statement("Maximize the conversion rate.")
    assert result["valid"] is False
    assert any("context" in issue for issue in result["issues"])


def test_suggestions_are_provided_for_invalid() -> None:
    result = evaluate_outcome_statement("Improve things when possible.")
    assert result["valid"] is False
    assert result["suggestions"]
