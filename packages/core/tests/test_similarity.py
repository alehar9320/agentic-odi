"""Tests for the statement normaliser and similarity score."""

from __future__ import annotations

import pytest
from agentic_odi_core.similarity import normalize, similar


def test_normalize_lowercases_and_drops_punctuation() -> None:
    assert normalize("Minimize the time it takes to onboard!") == "minimize time takes onboard"


def test_normalize_drops_stopwords_and_collapses_whitespace() -> None:
    assert normalize("  the   QUICK  brown fox  ") == "quick brown fox"


def test_normalize_of_stopwords_only_is_empty() -> None:
    assert normalize("the and of to") == ""


def test_normalize_is_pinned_to_the_documented_vocabulary() -> None:
    # "with" is a stopword, "without" is not; a change to the list breaks this.
    assert normalize("with care") == "care"
    assert normalize("without care") == "without care"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Minimize the time it takes to onboard", "minimize time it takes onboard"),
        ("Maximize the number of steps", "Maximize the number steps"),
    ],
)
def test_similar_collapses_word_order_and_stopwords(left: str, right: str) -> None:
    assert similar(left, right) == 1.0


def test_similar_is_zero_for_two_different_stopword_only_strings() -> None:
    assert similar("the and", "of to") == 0.0


def test_similar_is_one_for_identical_stopword_only_strings() -> None:
    assert similar("the and", " the and ") == 1.0


def test_similar_is_between_zero_and_one_for_partial_overlap() -> None:
    score = similar("Minimize the time to onboard", "Minimize the cost of support")
    assert 0.0 < score < 1.0


def test_similar_is_symmetric() -> None:
    left = "Minimize the time it takes to onboard a new hire"
    right = "Minimize onboarding time for new hires"
    assert similar(left, right) == similar(right, left)


def test_unrelated_statements_score_low() -> None:
    assert similar("Minimize the time to onboard", "Maximize revenue per account") < 0.5
