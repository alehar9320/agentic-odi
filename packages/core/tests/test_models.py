"""Tests for core domain models."""

from __future__ import annotations

import json
from itertools import product
from pathlib import Path

import pytest
from agentic_odi_core.models import (
    BusinessImpactCategory,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Direction,
    ValueMetric,
    compute_opportunity_score,
    explain_opportunity_score,
)

OPPORTUNITY_FIXTURE = Path(__file__).parent / "fixtures" / "opportunity_scores.json"
SCALE = [round(1 + index * 0.1, 1) for index in range(91)]


def _customer_value(**overrides: object) -> CustomerValue:
    data: dict[str, object] = {
        "direction": Direction.MINIMIZE,
        "unit_of_measure": "minutes",
        "object_of_control": "time to resolve a support ticket",
        "statement": "Minimize the time it takes to resolve a support ticket",
        "importance": 8.0,
        "satisfaction": 4.0,
    }
    data.update(overrides)
    return CustomerValue(**data)  # type: ignore[arg-type]


def test_customer_value_opportunity_score_is_computed() -> None:
    assert _customer_value().opportunity_score == 12.0


def test_value_metric_opportunity_score_is_computed() -> None:
    metric = ValueMetric(
        name="resolution time",
        direction=Direction.MINIMIZE,
        unit_of_measure="minutes",
        importance=9.0,
        satisfaction=2.0,
    )
    assert metric.opportunity_score == 16.0


def test_customer_outcome_delegates_opportunity_score() -> None:
    outcome = CustomerOutcome(
        job_id="job-1",
        customer_value=_customer_value(importance=6.0, satisfaction=1.0),
        business_value=BusinessValue(
            category=BusinessImpactCategory.COST_REDUCTION,
            statement="Reduce support cost",
        ),
    )
    assert outcome.opportunity_score == 11.0


def test_explain_opportunity_score_returns_the_worked_example() -> None:
    """The example the issue answers with: 8.6 + 3.7 = 12.3, on a 1-19 index."""
    explanation = explain_opportunity_score(8.6, 4.9)

    assert explanation["score"] == pytest.approx(12.3, abs=0.001)
    assert explanation["gap"] == pytest.approx(3.7, abs=0.001)
    assert explanation["importance"] == 8.6
    assert explanation["satisfaction"] == 4.9
    assert explanation["threshold"] == 10.0
    assert explanation["min_score"] == 1.0
    assert explanation["max_score"] == 19.0
    assert explanation["inputs_present"] is True
    assert explanation["method"] == "importance + max(importance - satisfaction, 0)"


def test_explain_opportunity_score_names_both_regimes() -> None:
    """A gap is charged only when importance outweighs satisfaction."""
    assert explain_opportunity_score(10, 1)["score"] == 19.0
    assert explain_opportunity_score(1, 1)["score"] == 1.0
    assert explain_opportunity_score(10, 10)["score"] == 10.0
    assert explain_opportunity_score(5, 10)["score"] == 5.0


def test_explain_opportunity_score_is_underserved_only_above_the_threshold() -> None:
    assert explain_opportunity_score(10, 10)["underserved"] is False
    assert explain_opportunity_score(10, 9.9)["underserved"] is True


def test_explain_opportunity_score_reports_absent_inputs_without_inventing_zeros() -> None:
    explanation = explain_opportunity_score(None, 4.0)

    assert explanation["inputs_present"] is False
    assert explanation["score"] is None
    assert explanation["gap"] is None
    assert explanation["underserved"] is False


def test_explain_opportunity_score_stays_inside_the_index_on_the_whole_grid() -> None:
    for importance, satisfaction in product(SCALE, repeat=2):
        explanation = explain_opportunity_score(importance, satisfaction)
        score = explanation["score"]
        assert score is not None
        assert 1.0 <= score <= 19.0, (importance, satisfaction)
        assert explanation["underserved"] is (score > 10.0), (importance, satisfaction)


def test_explain_opportunity_score_agrees_with_compute_opportunity_score() -> None:
    """One arithmetic, two shapes: the explanation never drifts from the float."""
    for importance, satisfaction in product(SCALE, repeat=2):
        explanation = explain_opportunity_score(importance, satisfaction)
        assert explanation["score"] == pytest.approx(
            compute_opportunity_score(importance, satisfaction), abs=0.001
        )


def test_shared_fixture_rows_are_explained_by_python() -> None:
    """The committed rows are the contract with the Studio's own copy."""
    rows = json.loads(OPPORTUNITY_FIXTURE.read_text())

    assert [row["score"] for row in rows] == [1.0, 19.0, 10.0, 5.0, 12.3]
    for row in rows:
        explanation = explain_opportunity_score(row["importance"], row["satisfaction"])
        assert explanation["score"] == pytest.approx(row["score"], abs=0.001), row
        assert explanation["underserved"] is row["underserved"], row
