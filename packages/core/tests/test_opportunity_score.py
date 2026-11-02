"""Regression tests for the ODI opportunity score.

``compute_opportunity_score`` implements the ODI formula on the 1-10 scale the
models enforce: ``importance + max(importance - satisfaction, 0)``. Every case
below is an independently computed expectation, so a change to the formula --
dropping the clamp, swapping the terms, or scaling the result -- fails a test.

The cases live in ``tests/fixtures/opportunity-score.json`` and are read by both
this test and ``apps/studio/src/lib/odi.test.ts``. One fixture, two languages:
a drift between the Python service and the TypeScript client fails CI on the
commit that caused it rather than on a customer's slide.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentic_odi_core.models import compute_opportunity_score

FIXTURE = Path(__file__).parent / "fixtures" / "opportunity-score.json"


def _load_cases() -> list[dict]:
    with FIXTURE.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data["cases"]


CASES = _load_cases()


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_fixture_cases(case: dict) -> None:
    importance = case["importance"]
    satisfaction = case["satisfaction"]
    expected = case["expected"]
    if importance is None or satisfaction is None:
        assert expected is None
        return
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