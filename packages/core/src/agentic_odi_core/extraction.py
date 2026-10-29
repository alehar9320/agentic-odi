"""Turn one stored quote into proposed outcome statements — never into outcomes.

The machine proposes; a person accepts. This module is the *candidate* half of
that rule: :class:`StatementExtractor` is a :class:`~typing.Protocol`, so core
gains no model dependency, and the default is a deterministic fixture used by
every test. The implementation that calls a model is injected by a caller that
already has a client.

Every proposal passes :func:`~agentic_odi_core.evaluation.evaluate_outcome_statement`
*before* it is stored. A proposal that fails is kept with ``status='rejected'``
and the validator's reason in ``rationale`` — discarding it would throw away the
evidence that the extractor is wrong.

Idempotency: candidates are keyed on ``(quote_id, normalised_statement)`` via
:func:`~agentic_odi_core.similarity.normalisation_key`, so re-extracting the same
quote adds nothing and never resets a person's decision.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from agentic_odi_core.evaluation import evaluate_outcome_statement
from agentic_odi_core.models import CandidateStatus, OutcomeCandidate
from agentic_odi_core.repository import Repository
from agentic_odi_core.similarity import normalisation_key

#: The prompt template for a model-backed extractor. It states the ODI outcome
#: format and bans solution framing, so a proposal that ignores the format is
#: caught by the validator rather than silently stored. Kept beside the protocol
#: so the two cannot drift.
EXTRACTION_PROMPT = """\
You turn one customer quote into ODI desired-outcome statements.

Rules:
- Write each statement as: <Minimize|Maximize> <unit of measure> <object of \
control> <contextual clarifier>.
- Start with "Minimize" or "Maximize". Name a unit of measure (time, cost, \
number, frequency, rate, errors, ...).
- State the context when it happens ("when ...", "while ...", "before ...").
- Describe the customer's problem, never a solution. Do not name a feature, \
screen, notification, dashboard, or product.
- Return at most {max_candidates} statements, each with a confidence in [0, 1].

Quote:
\"\"\"{quote}\"\"\"

Job: {job_name}
Stage hint: {stage_hint}
"""


@dataclass(frozen=True, slots=True)
class Proposal:
    """One proposed statement from an extractor, before validation."""

    statement: str
    rationale: str = ""
    confidence: float | None = None


@runtime_checkable
class StatementExtractor(Protocol):
    """Proposes outcome statements from one quote. Never writes to the store."""

    async def propose(
        self,
        quote: str,
        job_name: str | None = None,
        stage_hint: str | None = None,
    ) -> list[Proposal]: ...


class FixtureStatementExtractor:
    """A deterministic extractor for tests and the demo. No network, no model.

    It splits a quote into sentences and proposes each as a statement, so the
    fixture exercises the real validation and idempotency paths without a
    model call. The same quote always yields the same proposals.
    """

    def __init__(self, proposals: Sequence[Proposal] | None = None) -> None:
        self._proposals = list(proposals) if proposals is not None else None

    async def propose(
        self,
        quote: str,
        job_name: str | None = None,
        stage_hint: str | None = None,
    ) -> list[Proposal]:
        if self._proposals is not None:
            return list(self._proposals)
        return [Proposal(statement=sentence.strip()) for sentence in _split_sentences(quote)]


def _split_sentences(quote: str) -> list[str]:
    """Split a quote on sentence boundaries, dropping empties."""
    parts = re.split(r"(?<=[.!?])\s+", quote.strip())
    return [part for part in parts if part.strip()]


class ExtractionError(Exception):
    """The extractor returned a payload that cannot be used.

    Raised rather than guessed at: a malformed payload must not create a
    candidate or a partial invalid state.
    """


def _validate_proposals(proposals: object) -> list[Proposal]:
    """Coerce an extractor's return value into proposals, or refuse it.

    A malformed payload (not a list, an item that is not a proposal) is refused
    explicitly so it can never create a candidate. Confidence outside ``[0, 1]``
    is likewise refused here rather than clamped — a clamped confidence is a
    fabricated one.
    """
    if not isinstance(proposals, Iterable) or isinstance(proposals, (str, bytes)):
        raise ExtractionError(f"extractor returned {type(proposals).__name__}, expected a list")
    result: list[Proposal] = []
    for index, item in enumerate(proposals):
        if not isinstance(item, Proposal):
            raise ExtractionError(f"proposal {index} is {type(item).__name__}, expected Proposal")
        if item.confidence is not None and not (0.0 <= item.confidence <= 1.0):
            raise ExtractionError(
                f"proposal {index} confidence {item.confidence} is outside [0, 1]"
            )
        if not item.statement.strip():
            raise ExtractionError(f"proposal {index} has an empty statement")
        result.append(item)
    return result


async def extract_candidates(
    repo: Repository,
    extractor: StatementExtractor,
    *,
    quote_id: str,
    quote: str,
    job_id: str,
    job_name: str | None = None,
    stage_hint: str | None = None,
    interview_id: str | None = None,
    step_id: str | None = None,
) -> list[OutcomeCandidate]:
    """Extract proposals from one quote and persist them as candidates.

    Returns every candidate for the quote after the run — the newly created ones
    plus any already stored. Re-running is idempotent: a proposal whose
    ``(quote_id, normalised_statement)`` key already exists is skipped, so a
    person's accepted/rejected/merged decision is never reset.

    Raises :class:`ExtractionError` if the extractor returns a malformed payload.
    Raises ``ValueError`` if the quote is empty. Neither creates any candidate.
    """
    if not quote or not quote.strip():
        raise ValueError("cannot extract candidates from an empty quote")

    raw = await extractor.propose(quote, job_name, stage_hint)
    proposals = _validate_proposals(raw)

    existing = repo.list_candidates(quote_id=quote_id)
    seen = {normalisation_key(c.quote_id, c.statement) for c in existing}

    for proposal in proposals:
        key = normalisation_key(quote_id, proposal.statement)
        if key in seen:
            continue
        seen.add(key)
        verdict = evaluate_outcome_statement(proposal.statement)
        if verdict["valid"]:
            status = CandidateStatus.PROPOSED
            rationale = proposal.rationale
        else:
            status = CandidateStatus.REJECTED
            rationale = " ".join(verdict["issues"])
        repo.add_candidate(
            OutcomeCandidate(
                quote_id=quote_id,
                interview_id=interview_id,
                job_id=job_id,
                step_id=step_id,
                statement=proposal.statement,
                rationale=rationale,
                confidence=proposal.confidence,
                status=status,
            )
        )

    return repo.list_candidates(quote_id=quote_id)


__all__ = [
    "EXTRACTION_PROMPT",
    "ExtractionError",
    "FixtureStatementExtractor",
    "Proposal",
    "StatementExtractor",
    "extract_candidates",
]
