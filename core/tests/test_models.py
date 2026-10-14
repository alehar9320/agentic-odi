"""Tests for core domain models and ODI opportunity scoring."""

from __future__ import annotations

import pytest

from core.models import (
    BusinessImpactCategory,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Direction,
    ValueMetric,
    compute_opportunity_score,
)


@pytest.mark.parametrize(
    ("importance", "satisfaction", "expected"),
    [
        (8.0, 4.0, 12.0),
        (5.0, 5.0, 5.0),
        (3.0, 9.0, 3.0),
        (10.0, 1.0, 19.0),
    ],
)
def test_compute_opportunity_score(importance: float, satisfaction: float, expected: float) -> None:
    assert compute_opportunity_score(importance, satisfaction) == expected


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
