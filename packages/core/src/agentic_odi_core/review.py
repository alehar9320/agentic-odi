"""Turn a proposed candidate into a real outcome — or record why it is not one.

This is the *acceptance* half of the product's first rule: the machine proposes,
a person decides. Acceptance is the only path from a candidate to an
:class:`~agentic_odi_core.models.Outcome`, and it goes through
:meth:`~agentic_odi_core.services.ODIService.add_outcome`, so the statement
validator and the score rules still apply. A candidate can never smuggle an
unparseable statement into the store.

Four verbs are four states, and none of them is deletion:

* **accept** — create exactly one outcome, link it, write its verbatim quote as
  evidence, then flip the candidate.
* **edit** — change the statement, then accept.
* **merge** — fold into an existing outcome (``merged_into``), creating no new one.
* **reject** — record a required non-empty reason; the candidate is kept.

Rejecting or merging does not remove the candidate: a rejection is information
about the extractor, and a merge is information about duplicates.
"""

from __future__ import annotations

import logging

from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import CandidateStatus, ExtractedCandidate, Outcome
from agentic_odi_core.repository import Repository
from agentic_odi_core.services import (
    CandidateNotFoundError,
    JobNotFoundError,
    ODIService,
    OutcomeNotFoundError,
)

log = logging.getLogger(__name__)


class CandidateAlreadyDecidedError(ValidationError):
    """The candidate is not in ``proposed``, so it cannot be decided again."""

    def __init__(self, candidate_id: str, status: CandidateStatus) -> None:
        self.candidate_id = candidate_id
        self.status = status
        super().__init__(
            f"Candidate {candidate_id} is already {status.value}; "
            "only a proposed candidate can be decided."
        )


def _require_proposed(repo: Repository, candidate_id: str) -> ExtractedCandidate:
    candidate = repo.get_extracted_candidate(candidate_id)
    if candidate is None:
        raise CandidateNotFoundError(candidate_id)
    if candidate.status is not CandidateStatus.PROPOSED:
        raise CandidateAlreadyDecidedError(candidate_id, candidate.status)
    return candidate


def _record_quote_evidence(
    service: ODIService,
    repo: Repository,
    candidate: ExtractedCandidate,
    quote: str,
    outcome: Outcome,
) -> None:
    """Write the candidate's verbatim quote as an evidence row on ``outcome``."""
    interview = repo.get_interview(candidate.interview_id) if candidate.interview_id else None
    raw = {"candidate_id": candidate.id, "quote_id": candidate.quote_id}
    if candidate.interview_id is not None:
        raw["interview_id"] = candidate.interview_id
    service.add_evidence(
        source_name=interview.title if interview is not None else "Interview quote",
        source_kind="interview",
        name="quote",
        content=quote,
        item_type="manual",
        raw=raw,
        outcome_id=outcome.id,
    )


def accept_candidate(
    service: ODIService,
    repo: Repository,
    candidate_id: str,
    *,
    statement: str | None = None,
    importance: float,
    satisfaction: float,
    step_id: str | None = None,
) -> Outcome:
    """Accept a proposed candidate, creating exactly one outcome with its evidence.

    An edited ``statement`` replaces the proposed one; the outcome still passes
    the format validator via :meth:`ODIService.add_outcome`. The verbatim quote
    is written as an ``Evidence`` row tied to that outcome *before* the
    candidate is flipped, so a failure can never leave an accepted candidate
    without the sentence that produced it. A candidate that lost its quote is
    refused rather than accepted without provenance. The caller supplies the
    scores, because a person judges importance and satisfaction — the extractor
    does not invent them.
    """
    candidate = _require_proposed(repo, candidate_id)
    if candidate.job_id is None:
        raise ValidationError(
            f"Candidate {candidate_id} has no job_id; acceptance needs a job to attach to."
        )
    if repo.get_job(candidate.job_id) is None:
        raise JobNotFoundError(candidate.job_id)
    quote = (candidate.quote_text or "").strip()
    if not quote:
        raise ValidationError(
            f"Candidate {candidate_id} has no stored verbatim quote, so accepting it would "
            "lose its evidence. Re-extract it from its quote first."
        )

    resolved_statement = statement if statement is not None else candidate.statement
    outcome = service.add_outcome(
        job_id=candidate.job_id,
        statement=resolved_statement,
        importance=importance,
        satisfaction=satisfaction,
        step_id=step_id if step_id is not None else candidate.step_id,
    )
    try:
        _record_quote_evidence(service, repo, candidate, quote, outcome)
    except Exception as exc:
        # An outcome with no evidence is the one state acceptance must never
        # leave behind, so undo the write and let the caller see the failure.
        log.warning(
            "quote evidence could not be written; rolling back outcome %s (%s)",
            outcome.id,
            type(exc).__name__,
        )
        repo.delete_outcome(outcome.id)
        raise
    repo.update_extracted_candidate(
        candidate_id,
        {
            "status": CandidateStatus.ACCEPTED.value,
            "statement": resolved_statement,
            "outcome_id": outcome.id,
        },
    )
    return outcome


def reject_candidate(repo: Repository, candidate_id: str, *, reason: str) -> ExtractedCandidate:
    """Reject a proposed candidate. The reason is required and kept.

    Rejection is information about the extractor, so the candidate is retained
    with ``status='rejected'`` rather than deleted.
    """
    if not reason or not reason.strip():
        raise ValidationError("A rejection requires a non-empty reason.")
    _require_proposed(repo, candidate_id)
    updated = repo.update_extracted_candidate(
        candidate_id,
        {"status": CandidateStatus.REJECTED.value, "rejection_reason": reason.strip()},
    )
    if updated is None:
        # _require_proposed proved it exists, so this is a store that lost the
        # row between the read and the write, not a caller error.
        raise CandidateNotFoundError(candidate_id)
    return updated


def merge_candidate(
    repo: Repository,
    candidate_id: str,
    *,
    merged_into: str,
) -> ExtractedCandidate:
    """Fold a proposed candidate into an existing outcome. Creates no outcome.

    ``merged_into`` must be an outcome that exists; the candidate is flipped to
    ``merged`` and links the outcome via ``merged_into`` and ``outcome_id``.
    """
    candidate = _require_proposed(repo, candidate_id)
    target = repo.get_outcome(merged_into)
    if target is None:
        raise OutcomeNotFoundError(merged_into)
    if candidate.job_id is not None and target.job_id != candidate.job_id:
        raise ValidationError("merged_into outcome does not belong to the candidate's job")
    updated = repo.update_extracted_candidate(
        candidate_id,
        {
            "status": CandidateStatus.MERGED.value,
            "merged_into": merged_into,
            "outcome_id": merged_into,
        },
    )
    if updated is None:
        # The candidate was read a moment ago under _require_proposed, so a
        # missing row here means the store lost it, not that the id was wrong.
        raise CandidateNotFoundError(candidate_id)
    return updated


__all__ = [
    "CandidateAlreadyDecidedError",
    "CandidateNotFoundError",
    "accept_candidate",
    "merge_candidate",
    "reject_candidate",
]
