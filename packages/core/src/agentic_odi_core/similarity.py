"""Compare outcome statements by meaning, not by exact text.

Extraction produces a candidate per proposal; the same idea is often phrased
twice. This module gives one documented normaliser and one similarity score so
that "the same" is decided in exactly one place.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable

# Above this score two statements are close enough to *suggest* as duplicates.
# It is a suggestion, never a decision: a person chooses the merge target.
DUPLICATE_THRESHOLD = 0.82

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


def find_duplicate_groups(
    candidates: Iterable[object], threshold: float = DUPLICATE_THRESHOLD
) -> list[list[str]]:
    """Group near-duplicate candidates by id, without writing anything.

    ``candidates`` is anything with ``id`` and ``statement`` attributes (an
    :class:`~agentic_odi_core.models.OutcomeCandidate` qualifies). Two
    candidates are linked when :func:`similar` scores at or above ``threshold``;
    groups are the transitive closure of those links, so paraphrases that only
    match a neighbour still end up together.

    Only groups of two or more are returned, each sorted by id, and the groups
    are ordered by their smallest id — the same input always yields the same
    output. A match is a *suggestion*: the caller decides the merge target.
    """
    items = [(candidate.id, candidate.statement) for candidate in candidates]  # type: ignore[attr-defined]
    parent = {candidate_id: candidate_id for candidate_id, _ in items}

    def find(candidate_id: str) -> str:
        while parent[candidate_id] != candidate_id:
            parent[candidate_id] = parent[parent[candidate_id]]
            candidate_id = parent[candidate_id]
        return candidate_id

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            # Point the larger id at the smaller one so roots stay stable.
            low, high = sorted((left_root, right_root))
            parent[high] = low

    for index, (left_id, left_statement) in enumerate(items):
        for right_id, right_statement in items[index + 1 :]:
            if similar(left_statement, right_statement) >= threshold:
                union(left_id, right_id)

    groups: dict[str, list[str]] = {}
    for candidate_id, _ in items:
        groups.setdefault(find(candidate_id), []).append(candidate_id)
    return sorted(
        (sorted(group) for group in groups.values() if len(group) > 1),
        key=lambda group: group[0],
    )


def duplicate_suggestions(
    candidates: Iterable[object], threshold: float = DUPLICATE_THRESHOLD
) -> list[tuple[str, list[str]]]:
    """For each candidate with near-duplicates, its id and the other ids.

    A flat, per-candidate view of :func:`find_duplicate_groups` for callers that
    want to show "this one looks like these" beside a single row. Only the
    other members of a candidate's group are listed, never the candidate itself.
    """
    return [
        (candidate_id, [other for other in group if other != candidate_id])
        for group in find_duplicate_groups(candidates, threshold)
        for candidate_id in group
    ]
