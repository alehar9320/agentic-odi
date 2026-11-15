"""Propose desired-outcome statements from interview quotes.

Extraction is deliberately behind a Protocol so the core never depends on a
model provider: the fixture extractor is the default, and a real one can be
injected without touching the service. Every proposal is validated before it is
stored, so a bad proposal is kept as a visible ``rejected`` candidate rather
than silently dropped or written as an outcome.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from agentic_odi_core.models import Interview, InterviewQuote


@dataclass(frozen=True)
class Proposal:
    """One candidate statement, with the extractor's own confidence and note."""

    statement: str
    confidence: float = 0.5
    rationale: str = ""


@runtime_checkable
class StatementExtractor(Protocol):
    """Turn one quote into zero or more candidate statements.

    Implementations must not write to a store. They return proposals; the
    service decides what is persisted.
    """

    def propose(
        self,
        quote: InterviewQuote,
        interview: Interview,
        stage_hint: str | None = None,
    ) -> list[Proposal]: ...


# A statement that already reads as an ODI outcome passes through; anything
# else is reshaped into the "Minimize the time it takes to …" form.
_DIRECTIONS = ("minimize", "maximize")


class FixtureExtractor:
    """A deterministic extractor for tests and offline runs.

    It splits a quote into sentences, keeps the ones that look like a need, and
    rewrites them into candidate statements. It is not a language model; it is
    the contract the real extractor must satisfy.
    """

    def __init__(self, proposals: dict[str, list[Proposal]] | None = None) -> None:
        """``proposals`` maps quote text to a fixed list, for scripted tests."""
        self._scripted = proposals or {}

    def propose(
        self,
        quote: InterviewQuote,
        interview: Interview,
        stage_hint: str | None = None,
    ) -> list[Proposal]:
        if quote.text in self._scripted:
            return list(self._scripted[quote.text])
        return [
            Proposal(statement=_to_statement(sentence), confidence=0.5)
            for sentence in _sentences(quote.text)
        ]


def _sentences(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text.strip())]
    return [part for part in parts if part]


def _to_statement(sentence: str) -> str:
    """Rewrite a complaint into the "Minimize/Maximize … when …" shape."""
    cleaned = sentence.strip().rstrip(".!?")
    if not cleaned:
        return cleaned
    lowered = cleaned.lower()
    if lowered.startswith(_DIRECTIONS):
        return cleaned[0].upper() + cleaned[1:]
    return f"Minimize the time it takes to {lowered}"
