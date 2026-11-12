"""The one text normaliser the product uses to decide two statements match.

Extraction is idempotent on ``(quote_id, normalised_statement)``: re-running an
extractor over the same quote must add nothing. Duplicate merge (``A6``) groups
candidates by the same key. Both need the *same* answer to "are these the same
statement", so the normaliser lives in exactly one place — here — rather than
being reimplemented per caller.

The transformation is deliberately lossy and stable:

1. lowercase,
2. Unicode NFKC, then punctuation and symbol removal,
3. whitespace collapse,
4. stopword removal.

Stopwords are removed for *comparison* only; the stored statement keeps the
reader's words. A statement that normalises to nothing (for example ``"the"``)
falls back to its punctuation-stripped text, and if that too is empty, to a
stable marker — so two different empty-normalising statements never collide
into one idempotency key.
"""

from __future__ import annotations

import re
import unicodedata

#: Words dropped before comparison. Kept small and explicit on purpose: a large
#: list silently merges statements that a person would read as different, and a
#: merge is not reversible. This is the whole vocabulary — there is no second
#: list anywhere else in the product.
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
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "so",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "you",
        "your",
    }
)

#: Marker used when a statement has no comparable content at all, so an
#: all-stopword statement still gets a distinct, stable key.
EMPTY_NORMALISED = "\x00empty"

_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+", re.UNICODE)


def _strip_punctuation(text: str) -> str:
    """Lowercase, NFKC-normalise, drop punctuation/symbols, collapse whitespace."""
    folded = unicodedata.normalize("NFKC", text).lower()
    without_punctuation = _PUNCTUATION.sub(" ", folded)
    return _WHITESPACE.sub(" ", without_punctuation).strip()


def normalise(text: str) -> str:
    """Return the comparison form of ``text``.

    Lowercase, punctuation-free, stopword-free, single-spaced. An input that
    has no content after punctuation removal returns :data:`EMPTY_NORMALISED`;
    an input whose words are all stopwords falls back to its punctuation-stripped
    text, so ``"the time"`` and ``"the cost"`` stay distinct even though both
    lose their stopwords.
    """
    stripped = _strip_punctuation(text)
    if not stripped:
        return EMPTY_NORMALISED
    words = [word for word in stripped.split(" ") if word and word not in STOPWORDS]
    if words:
        return " ".join(words)
    return stripped


def is_same_statement(left: str, right: str) -> bool:
    """Whether two statements normalise to the same comparison form."""
    return normalise(left) == normalise(right)


def normalisation_key(quote_id: str, statement: str) -> tuple[str, str]:
    """The idempotency key for a candidate: its quote and its normalised statement.

    Extraction is keyed on this pair, so re-extracting the same quote produces
    the same keys and therefore adds no candidates.
    """
    return (quote_id, normalise(statement))


__all__ = [
    "EMPTY_NORMALISED",
    "STOPWORDS",
    "is_same_statement",
    "normalisation_key",
    "normalise",
]
