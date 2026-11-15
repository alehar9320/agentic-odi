"""Compare outcome statements by meaning, not by exact text.

Extraction produces a candidate per proposal; the same idea is often phrased
twice. This module gives one documented normaliser and one similarity score so
that "the same" is decided in exactly one place.
"""

from __future__ import annotations

import difflib
import re

# Pinned vocabulary. Changing this list changes what counts as a duplicate, so
# it is treated as a contract: add words deliberately, with a test that shows
# the intended collapse or non-collapse.
STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "were",
        "when",
        "which",
        "with",
    }
)

_PUNCTUATION = re.compile(r"[^\w\s]")
_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, drop stopwords, collapse whitespace.

    The result is the key used to decide whether two statements are the same
    idea. It is deliberately lossy: ``"Minimize the time it takes to onboard"``
    normalises to ``"minimize time takes onboard"``.
    """
    lowered = text.lower()
    without_punctuation = _PUNCTUATION.sub(" ", lowered)
    tokens = [token for token in without_punctuation.split() if token not in STOPWORDS]
    return _WHITESPACE.sub(" ", " ".join(tokens)).strip()


def similar(left: str, right: str) -> float:
    """Return a similarity in ``[0, 1]`` between two statements.

    The score is the mean of two signals: token-set overlap (Jaccard) and
    :class:`difflib.SequenceMatcher` on the normalised text. Token overlap
    catches word-order changes; the sequence ratio catches partial edits.

    When both statements normalise to empty there is no content to compare, so
    the score is ``1.0`` only when the raw strings are identical and ``0.0``
    otherwise — two different stopword-only strings are not "the same".
    """
    left_normalized = normalize(left)
    right_normalized = normalize(right)
    if not left_normalized or not right_normalized:
        if left.strip() == right.strip():
            return 1.0
        return 0.0
    if left_normalized == right_normalized:
        return 1.0

    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    union = left_tokens | right_tokens
    overlap = len(left_tokens & right_tokens) / len(union) if union else 0.0
    ratio = difflib.SequenceMatcher(None, left_normalized, right_normalized).ratio()
    return (overlap + ratio) / 2
