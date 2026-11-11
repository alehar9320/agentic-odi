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


# -- The published rubric (#342) ----------------------------------------------


def test_the_rubric_publishes_every_rule_the_verdict_reports() -> None:
    rubric = outcome_rubric()

    assert rubric["version"] == 1
    rule_ids = {rule["id"] for rule in rubric["rules"]}
    check_ids = {check["id"] for check in evaluate_outcome_statement("")["checks"]}
    assert rule_ids == check_ids
    assert len(rubric["rules"]) == 8


def test_every_published_rule_carries_its_guidance_and_examples() -> None:
    for rule in outcome_rubric()["rules"]:
        assert rule["id"]
        assert rule["label"]
        assert rule["summary"]
        assert rule["fix"]
        assert rule["examples"]["good"]
        assert rule["examples"]["bad"]


def test_every_rule_flips_ok_on_its_own_failing_example() -> None:
    # Each rule's own "bad" example is the statement that fails it. The rule
    # must report not-ok for that statement and carry its id and fix, while
    # the statement as a whole may fail other rules too.
    for rule in outcome_rubric()["rules"]:
        checks = {
            check["id"]: check
            for check in evaluate_outcome_statement(rule["examples"]["bad"])["checks"]
        }
        failed = checks[rule["id"]]
        assert failed["ok"] is False, f"rule {rule['id']} did not flag its own bad example"
        assert failed["fix"] == rule["fix"]
        assert failed["message"]


def test_every_rule_passes_on_the_well_formed_statement() -> None:
    checks = evaluate_outcome_statement(WELL_FORMED)["checks"]

    assert checks
    assert all(check["ok"] is True for check in checks)
    assert all(check["message"] is None for check in checks)


def test_a_statement_breaking_three_rules_names_three_failing_checks() -> None:
    # "Minimize the time better" fails the context, length-floor, and vague-term
    # rules at once, and passes the other five.
    checks = evaluate_outcome_statement("Minimize the time better")["checks"]
    failing = [check for check in checks if check["ok"] is False]

    assert {check["id"] for check in failing} == {
        "contextual_clarifier",
        "min_words",
        "vague_terms",
    }
    assert all(check["fix"] for check in failing)


def test_checks_match_issues_and_suggestions_one_to_one() -> None:
    for statement in (WELL_FORMED, "Make it faster", "I want a notification", "   "):
        result = evaluate_outcome_statement(statement)
        failing = [check for check in result["checks"] if check["ok"] is False]
        assert [check["message"] for check in failing] == result["issues"]
        assert [check["fix"] for check in failing] == result["suggestions"]


def test_the_rubric_is_derived_from_the_validator_constants() -> None:
    # A constant edit that changes a check changes the published rubric with it:
    # the summary names the same directions, units, vague terms, and bounds the
    # validator reads, so a hand-copied second list cannot drift.
    from agentic_odi_core.evaluation import (
        _CONTEXT_MARKERS,
        _DIRECTIONS,
        _MAX_CHARS,
        _MIN_WORDS,
        _SOLUTION_NOUNS,
        _UNITS,
        _VAGUE_TERMS,
    )

    rules = {rule["id"]: rule for rule in outcome_rubric()["rules"]}
    assert all(direction in rules["direction"]["summary"] for direction in _DIRECTIONS)
    assert all(unit in rules["unit_of_measure"]["summary"] for unit in _UNITS)
    assert all(term in rules["vague_terms"]["summary"] for term in _VAGUE_TERMS)
    assert all(noun in rules["solution_nouns"]["summary"] for noun in _SOLUTION_NOUNS)
    assert all(
        marker.strip() in rules["contextual_clarifier"]["summary"] for marker in _CONTEXT_MARKERS
    )
    assert str(_MIN_WORDS) in rules["min_words"]["summary"]
    assert str(_MAX_CHARS) in rules["max_chars"]["summary"]
