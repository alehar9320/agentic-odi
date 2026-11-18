"""Regression tests for the ODI opportunity score.

``compute_opportunity_score`` implements the ODI formula on the 1-10 scale the
models enforce: ``importance + max(importance - satisfaction, 0)``. Every case
below is an independently computed expectation, so a change to the formula --
dropping the clamp, swapping the terms, or scaling the result -- fails a test.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.models import (
    CONFIDENCE_WEIGHTS,
    OUTCOME_INPUT_MIN,
    compute_opportunity_score,
    confidence_weighted_inputs,
)


@pytest.mark.parametrize(
    ("importance", "satisfaction", "expected"),
    [
        (10.0, 1.0, 19.0),
        (8.0, 4.0, 12.0),
        (5.0, 5.0, 5.0),
        (3.0, 9.0, 3.0),
        (1.0, 1.0, 1.0),
        (10.0, 10.0, 10.0),
        (7.5, 2.5, 12.5),
        (2.0, 1.5, 2.5),
    ],
)
def test_adds_the_underserved_gap_to_importance(
    importance: float, satisfaction: float, expected: float
) -> None:
    assert compute_opportunity_score(importance, satisfaction) == expected


def test_a_satisfied_need_never_subtracts_from_importance() -> None:
    for importance in (1.0, 5.0, 10.0):
        for satisfaction in (1.0, 5.0, 10.0):
            score = compute_opportunity_score(importance, satisfaction)
            assert score >= importance


def test_raising_importance_never_lowers_the_score() -> None:
    for importance in (0.0, 2.5, 7.0):
        lower = compute_opportunity_score(importance, 4.0)
        higher = compute_opportunity_score(importance + 0.5, 4.0)
        assert higher >= lower


def test_raising_satisfaction_never_raises_the_score() -> None:
    for satisfaction in (1.0, 4.0, 9.0):
        before = compute_opportunity_score(4.0, satisfaction)
        after = compute_opportunity_score(4.0, satisfaction + 0.5)
        assert after <= before


def test_returns_a_float_even_for_integer_inputs() -> None:
    score = compute_opportunity_score(5, 3)  # type: ignore[arg-type]
    assert isinstance(score, float)
    assert score == 7.0


# -- Evidence confidence weights the inputs, never the score -------------------


def test_verified_weighs_more_than_claimed() -> None:
    assert CONFIDENCE_WEIGHTS["verified"] > CONFIDENCE_WEIGHTS["claimed"]
    assert CONFIDENCE_WEIGHTS["verified"] == 1.0
    assert CONFIDENCE_WEIGHTS["claimed"] == 0.5


def test_verified_inputs_are_unchanged_and_claimed_inputs_are_halved() -> None:
    assert confidence_weighted_inputs(8.0, 4.0, "verified") == (8.0, 4.0)
    assert confidence_weighted_inputs(8.0, 4.0, "claimed") == (4.0, 2.0)


def test_an_unknown_confidence_weighs_as_claimed() -> None:
    assert confidence_weighted_inputs(8.0, 4.0, "maybe") == confidence_weighted_inputs(
        8.0, 4.0, "claimed"
    )


def test_weighted_inputs_never_fall_below_the_model_floor() -> None:
    #: Claimed halves 1.0 to 0.5, which is below the Outcome's 1.0 lower bound.
    weighted = confidence_weighted_inputs(1.0, 1.0, "claimed")
    assert weighted == (OUTCOME_INPUT_MIN, OUTCOME_INPUT_MIN)


def test_the_helper_is_a_pure_function_of_its_arguments() -> None:
    first = confidence_weighted_inputs(9.0, 3.0, "claimed")
    second = confidence_weighted_inputs(9.0, 3.0, "claimed")
    assert first == second


def test_verified_evidence_outranks_claimed_on_identical_inputs() -> None:
    raw_importance, raw_satisfaction = 8.0, 4.0
    verified = compute_opportunity_score(
        *confidence_weighted_inputs(raw_importance, raw_satisfaction, "verified")
    )
    claimed = compute_opportunity_score(
        *confidence_weighted_inputs(raw_importance, raw_satisfaction, "claimed")
    )
    assert verified > claimed


def test_only_verified_evidence_can_cross_ten_on_the_same_inputs() -> None:
    raw_importance, raw_satisfaction = 8.0, 4.0
    verified = compute_opportunity_score(
        *confidence_weighted_inputs(raw_importance, raw_satisfaction, "verified")
    )
    claimed = compute_opportunity_score(
        *confidence_weighted_inputs(raw_importance, raw_satisfaction, "claimed")
    )
    assert verified > 10.0
    assert claimed <= 10.0
