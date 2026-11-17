"""The outcome format guard: what it accepts, and what it refuses to bless."""

from __future__ import annotations

from agentic_odi_core.evaluation import evaluate_outcome_statement, outcome_rubric

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


def test_outcome_rubric_returns_all_eight_rules() -> None:
    rubric = outcome_rubric()

    assert rubric["version"] == "1"
    assert len(rubric["rules"]) == 8
    rule_ids = [rule["id"] for rule in rubric["rules"]]
    expected_ids = [
        "direction",
        "unit_of_measure",
        "object_of_control",
        "contextual_clarifier",
        "min_words",
        "max_chars",
        "vague_terms",
        "solution_nouns",
    ]
    assert rule_ids == expected_ids
    for rule in rubric["rules"]:
        assert "id" in rule
        assert "label" in rule
        assert "summary" in rule
        assert "fix" in rule
        assert "examples" in rule
        assert "good" in rule["examples"]
        assert "bad" in rule["examples"]


def test_evaluate_outcome_statement_returns_checks_for_each_rule() -> None:
    result = evaluate_outcome_statement(WELL_FORMED)

    assert "checks" in result
    assert len(result["checks"]) == 8
    check_ids = [check["id"] for check in result["checks"]]
    expected_ids = [
        "direction",
        "unit_of_measure",
        "object_of_control",
        "contextual_clarifier",
        "min_words",
        "max_chars",
        "vague_terms",
        "solution_nouns",
    ]
    assert check_ids == expected_ids
    for check in result["checks"]:
        assert "id" in check
        assert "ok" in check
        assert "message" in check
        assert "fix" in check


def test_valid_statement_has_all_checks_ok() -> None:
    result = evaluate_outcome_statement(WELL_FORMED)

    assert result["valid"] is True
    for check in result["checks"]:
        assert check["ok"] is True
        assert check["message"] == ""
        assert check["fix"] == ""


def test_invalid_statement_has_failing_checks_with_messages() -> None:
    result = evaluate_outcome_statement("Make it faster")

    assert result["valid"] is False
    failing_checks = [check for check in result["checks"] if not check["ok"]]
    assert len(failing_checks) >= 3  # direction, vague_terms, min_words at minimum
    for check in failing_checks:
        assert check["message"]
        assert check["fix"]


def test_statement_breaking_three_rules_returns_three_failing_checks() -> None:
    # Has direction, unit, object - but missing context, too short, vague term
    result = evaluate_outcome_statement("Maximize the time faster")

    assert result["valid"] is False
    failing_checks = [check for check in result["checks"] if not check["ok"]]
    assert len(failing_checks) == 3
    failing_ids = {check["id"] for check in failing_checks}
    assert "contextual_clarifier" in failing_ids
    assert "min_words" in failing_ids
    assert "vague_terms" in failing_ids


def test_rubric_parity_with_evaluate_outcome_statement() -> None:
    """Every rule in outcome_rubric() must be produced by evaluate_outcome_statement and vice versa."""
    rubric = outcome_rubric()
    rubric_ids = {rule["id"] for rule in rubric["rules"]}

    result = evaluate_outcome_statement(WELL_FORMED)
    check_ids = {check["id"] for check in result["checks"]}

    assert rubric_ids == check_ids


def test_rubric_constants_not_hand_copied() -> None:
    """Verify rubric values are derived from validator constants, not hand-copied."""
    rubric = outcome_rubric()

    # Check min_words rule references _MIN_WORDS constant value
    min_words_rule = next(rule for rule in rubric["rules"] if rule["id"] == "min_words")
    assert str(6) in min_words_rule["summary"]  # _MIN_WORDS = 6

    # Check max_chars rule references _MAX_CHARS constant value
    max_chars_rule = next(rule for rule in rubric["rules"] if rule["id"] == "max_chars")
    assert str(200) in max_chars_rule["summary"]  # _MAX_CHARS = 200

    # Check vague_terms rule references _VAGUE_TERMS
    vague_terms_rule = next(rule for rule in rubric["rules"] if rule["id"] == "vague_terms")
    for term in ("better", "improve", "optimize", "faster", "easier"):
        assert term in vague_terms_rule["summary"]

    # Check solution_nouns rule references _SOLUTION_NOUNS
    solution_nouns_rule = next(rule for rule in rubric["rules"] if rule["id"] == "solution_nouns")
    for noun in (
        "notification",
        "dashboard",
        "button",
        "feature",
        "screen",
        "email",
        "workflow",
        "integration",
        "report",
        "toggle",
    ):
        assert noun in solution_nouns_rule["summary"]

    # Check direction rule references _DIRECTIONS
    direction_rule = next(rule for rule in rubric["rules"] if rule["id"] == "direction")
    for direction in ("minimize", "maximize"):
        assert direction in direction_rule["summary"].lower()

    # Check contextual_clarifier rule references _CONTEXT_MARKERS
    contextual_rule = next(rule for rule in rubric["rules"] if rule["id"] == "contextual_clarifier")
    for marker in ("when", "while", "before", "after", "during", "if", "as"):
        assert marker in contextual_rule["summary"]
