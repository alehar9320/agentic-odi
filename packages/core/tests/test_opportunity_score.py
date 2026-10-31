"""Regression tests for the ODI opportunity score.

``compute_opportunity_score`` implements the ODI formula on the 1-10 scale the
models enforce: ``importance + max(importance - satisfaction, 0)``. Every case
below is an independently computed expectation, so a change to the formula --
dropping the clamp, swapping the terms, or scaling the result -- fails a test.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.models import compute_opportunity_score


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
