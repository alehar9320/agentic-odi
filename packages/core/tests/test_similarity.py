"""Tests for the shared statement normaliser."""

from __future__ import annotations

from agentic_odi_core.similarity import (
    EMPTY_NORMALISED,
    is_same_statement,
    normalisation_key,
    normalise,
)


def test_normalise_is_case_and_punctuation_insensitive() -> None:
    assert normalise("Minimize the TIME it takes!") == normalise("minimize time it takes")


def test_normalise_removes_stopwords() -> None:
    assert normalise("the time it takes") == "time takes"


def test_normalise_keeps_distinct_content() -> None:
    assert normalise("the time") != normalise("the cost")


def test_normalise_collapses_whitespace() -> None:
    assert normalise("  minimize   the\n time  ") == normalise("minimize time")


def test_normalise_empty_input_uses_marker() -> None:
    assert normalise("") == EMPTY_NORMALISED
    assert normalise("   ") == EMPTY_NORMALISED
    assert normalise("!!!") == EMPTY_NORMALISED


def test_all_stopword_statement_falls_back_to_stripped_text() -> None:
    # "the" has no comparable content, but two different all-stopword inputs
    # must not collide into one key.
    assert normalise("the") == "the"
    assert normalise("the") != normalise("of")


def test_is_same_statement() -> None:
    assert is_same_statement("Minimize the time!", "minimize time")
    assert not is_same_statement("Minimize the time", "Maximize the time")


def test_normalisation_key_is_quote_scoped() -> None:
    assert normalisation_key("q1", "Minimize the time") != normalisation_key(
        "q2", "Minimize the time"
    )
    assert normalisation_key("q1", "Minimize the time!") == normalisation_key(
        "q1", "minimize  time"
    )
