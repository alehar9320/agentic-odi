"""Turn a proposed candidate into a real outcome — or record why it is not one.

This is the *acceptance* half of the product's first rule: the machine proposes,
a person decides. Acceptance is the only path from a candidate to an
:class:`~agentic_odi_core.models.Outcome`, and it goes through
:meth:`~agentic_odi_core.services.ODIService.add_outcome`, so the statement
validator and the score rules still apply. A candidate can never smuggle an
unparseable statement into the store.

Four verbs are four states, and none of them is deletion:

* **accept** — create exactly one outcome, link it, flip the candidate.
* **edit** — change the statement, then accept.
* **merge** — fold into an existing outcome (``merged_into``), creating no new one.
* **reject** — record a required non-empty reason; the candidate is kept.

Rejecting or merging does not remove the candidate: a rejection is information
about the extractor, and a merge is information about duplicates.
"""

from __future__ import annotations

from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import CandidateStatus, Outcome, OutcomeCandidate
from agentic_odi_core.repository import Repository
from agentic_odi_core.services import (
    JobNotFoundError,
    ODIService,
    OutcomeNotFoundError,
)


class CandidateNotFoundError(ValidationError):
    """No candidate has that id."""

    def __init__(self, candidate_id: str) -> None:
        self.candidate_id = candidate_id
        super().__init__(f"Candidate not found: {candidate_id}")


class CandidateAlreadyDecidedError(ValidationError):
    """The candidate is not in ``proposed``, so it cannot be decided again."""

    def __init__(self, candidate_id: str, status: CandidateStatus) -> None:
        self.candidate_id = candidate_id
        self.status = status
        super().__init__(
            f"Candidate {candidate_id} is already {status.value}; "
            "only a proposed candidate can be decided."
        )


def _require_proposed(repo: Repository, candidate_id: str) -> OutcomeCandidate:
    candidate = repo.get_candidate(candidate_id)
    if candidate is None:
        raise CandidateNotFoundError(candidate_id)
    if candidate.status is not CandidateStatus.PROPOSED:
        raise CandidateAlreadyDecidedError(candidate_id, candidate.status)
    return candidate


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
    """Accept a proposed candidate, creating exactly one outcome.

    An edited ``statement`` replaces the proposed one; the outcome still passes
    the format validator via :meth:`ODIService.add_outcome`. The candidate is
    flipped to ``accepted`` with the new ``outcome_id``. The caller supplies the
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

    resolved_statement = statement if statement is not None else candidate.statement
    outcome = service.add_outcome(
        job_id=candidate.job_id,
        statement=resolved_statement,
        importance=importance,
        satisfaction=satisfaction,
        step_id=step_id if step_id is not None else candidate.step_id,
    )
    repo.update_candidate(
        candidate_id,
        {
            "status": CandidateStatus.ACCEPTED.value,
            "statement": resolved_statement,
            "outcome_id": outcome.id,
        },
    )
    return outcome


def reject_candidate(repo: Repository, candidate_id: str, *, reason: str) -> OutcomeCandidate:
    """Reject a proposed candidate. The reason is required and kept.

    Rejection is information about the extractor, so the candidate is retained
    with ``status='rejected'`` rather than deleted.
    """
    if not reason or not reason.strip():
        raise ValidationError("A rejection requires a non-empty reason.")
    _require_proposed(repo, candidate_id)
    updated = repo.update_candidate(
        candidate_id,
        {"status": CandidateStatus.REJECTED.value, "rejection_reason": reason.strip()},
    )
    assert updated is not None  # _require_proposed proved it exists
    return updated


def merge_candidate(
    repo: Repository,
    candidate_id: str,
    *,
    merged_into: str,
) -> OutcomeCandidate:
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
    updated = repo.update_candidate(
        candidate_id,
        {
            "status": CandidateStatus.MERGED.value,
            "merged_into": merged_into,
            "outcome_id": merged_into,
        },
    )
    assert updated is not None
    return updated


__all__ = [
    "CandidateAlreadyDecidedError",
    "CandidateNotFoundError",
    "accept_candidate",
    "merge_candidate",
    "reject_candidate",
]
