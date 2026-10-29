"""Unit tests for scripts/coverage_floor.py (issue #88)."""

from __future__ import annotations

import pytest
from coverage_floor import compare, floor_from_toml


def test_reads_the_floor_from_pyproject_text() -> None:
    text = "[tool.coverage.report]\nshow_missing = true\nfail_under = 89\n"

    assert floor_from_toml(text) == 89.0


def test_a_missing_floor_is_an_error() -> None:
    with pytest.raises(ValueError, match="fail_under"):
        floor_from_toml("[tool.coverage.report]\nshow_missing = true\n")


def test_a_lowered_floor_is_rejected() -> None:
    assert compare(head=88, base=89) == "the coverage floor may not be lowered: 88% < 89%"


def test_an_equal_or_higher_floor_is_accepted() -> None:
    assert compare(head=89, base=89) is None
    assert compare(head=90, base=89) is None
