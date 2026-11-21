"""Deterministic bands (B3) pinned against hand-computed fixtures."""

from __future__ import annotations

import pytest
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import compute_opportunity_score
from agentic_odi_core.stats import Interval, opportunity_interval, percentile


def test_identical_inputs_give_identical_intervals() -> None:
    a = opportunity_interval([8.0, 6.0, 9.0], [4.0, 5.0, 3.0])
    b = opportunity_interval([8.0, 6.0, 9.0], [4.0, 5.0, 3.0])

    assert a == b
    assert isinstance(a, Interval)


def test_mid_is_the_score_of_the_means() -> None:
    interval = opportunity_interval([8.0, 6.0], [4.0, 6.0])

    assert interval.mid == compute_opportunity_score(7.0, 5.0)


def test_bounds_are_finite_and_ordered() -> None:
    interval = opportunity_interval([8.0, 6.0, 9.0, 3.0], [4.0, 5.0, 3.0, 8.0])

    assert interval.low <= interval.high
    assert all(
        value == value and abs(value) != float("inf") for value in (interval.low, interval.high)
    )


def test_constant_data_collapses_to_the_point() -> None:
    interval = opportunity_interval([7.0, 7.0, 7.0], [7.0, 7.0, 7.0])

    assert interval.low == interval.high == interval.mid == 7.0


def test_a_single_observation_is_a_zero_width_band() -> None:
    interval = opportunity_interval([8.0], [6.0])

    assert interval.low == interval.high == compute_opportunity_score(8.0, 6.0)
    assert interval.n == 1


def test_unequal_lengths_fail_explicitly() -> None:
    with pytest.raises(ValidationError):
        opportunity_interval([8.0, 6.0], [4.0])


def test_nonfinite_and_out_of_scale_observations_fail() -> None:
    with pytest.raises(ValidationError):
        opportunity_interval([float("nan")], [4.0])
    with pytest.raises(ValidationError):
        opportunity_interval([11.0], [4.0])
    with pytest.raises(ValidationError):
        opportunity_interval([0.5], [4.0])


def test_an_empty_sample_is_refused_not_answered_with_a_band() -> None:
    with pytest.raises(ValidationError):
        opportunity_interval([], [])


def test_invalid_sample_count_fails() -> None:
    with pytest.raises(ValidationError):
        opportunity_interval([8.0, 6.0], [4.0, 5.0], samples=0)


def test_percentile_interpolates_linearly() -> None:
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert percentile([5.0], 0.9) == 5.0
