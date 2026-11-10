"""Tests for merging duplicate candidate evidence into one outcome (A5.1b).

The interesting cases are the boundaries: paraphrases that are suggested but
never auto-merged, a repeated merge that changes nothing, a source that is a
settled decision, and an evidence write that fails part-way. Detection must be
read-only, so these tests also assert the store is untouched by suggestions.
"""

from __future__ import annotations

import pytest
from agentic_odi_core import (
    DUPLICATE_THRESHOLD,
    CandidateNotFoundError,
    CandidateStatus,
    InMemoryRepository,
    ODIService,
    OutcomeNotFoundError,
    find_duplicate_groups,
    similar,
)
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.extraction import Proposal
from agentic_odi_core.sqlite_repository import SQLiteRepository

# Five paraphrases of one need. Each is a valid ODI statement and they must all
# land in one suggestion group so a reviewer can merge them into one outcome.
PARAPHRASES = [
    "Minimize the time it takes to onboard when a new hire starts",
    "Minimize the time it takes to onboard when a new hire joins",
    "Minimize the time it takes to onboard when a new hire arrives",
    "Minimize the time it takes to onboard when a new hire onboards",
    "Minimize the time it takes to onboard when a new hire starts work",
]
UNRELATED = "Maximize the number of accounts created when onboarding"


class ScriptedExtractor:
    """Returns a fixed list of proposals, ignoring the quote."""

    def __init__(self, proposals: list[Proposal]) -> None:
        self._proposals = proposals

    def propose(self, quote, interview, stage_hint=None):  # noqa: ANN001, ANN201
        return list(self._proposals)


class FailingEvidenceRepository(InMemoryRepository):
    """Fails the third evidence write, so a merge is rolled back mid-way.

    Write 1 is the acceptance that establishes the target outcome; write 2 is
    the first merge source, which must succeed so the failure lands *after* one
    source has already been absorbed. That partial state is exactly what the
    rollback has to undo.
    """

    def __init__(self) -> None:
        super().__init__()
        self.evidence_writes = 0

    def add_evidence(self, evidence):  # noqa: ANN001, ANN201
        self.evidence_writes += 1
        if self.evidence_writes > 2:
            raise RuntimeError("evidence store unavailable")
        return super().add_evidence(evidence)


@pytest.fixture
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _seed(
    service: ODIService,
    statements: list[str],
    *,
    title: str = "Ana onboarding",
    participant: str = "Ana",
) -> tuple[str, list]:
    """Seed one interview with a quote per statement, and one candidate each.

    Each statement gets its own quote so a merge can be checked to attach
    *distinct* quote evidence links, not five copies of one quote.
    """
    job = service.add_job("Onboard")
    interview = service.add_interview(title=title, participant_label=participant, job_id=job.id)
    candidates = []
    for statement in statements:
        quote = service.add_quote(interview_id=interview.id, text=f"{statement}.")
        candidates.extend(
            service.extract_candidates(quote.id, ScriptedExtractor([Proposal(statement, 0.9)]))
        )
    return job.id, candidates


def _accepted_outcome(service: ODIService, candidate_id: str):
    """Accept a candidate and return the outcome it produced."""
    _, outcome, _ = service.accept_candidate(candidate_id, importance=8.0, satisfaction=3.0)
    return outcome


def test_similarity_puts_paraphrases_together_and_keeps_unrelated_apart() -> None:
    for statement in PARAPHRASES[1:]:
        assert similar(PARAPHRASES[0], statement) >= DUPLICATE_THRESHOLD
    assert similar(PARAPHRASES[0], UNRELATED) < DUPLICATE_THRESHOLD


def test_suggestions_are_read_only_and_group_the_paraphrases(service: ODIService) -> None:
    _, candidates = _seed(service, [*PARAPHRASES, UNRELATED])
    before = {candidate.id: candidate.status for candidate in service.list_candidates()}

    groups = service.suggest_duplicate_groups()

    assert len(groups) == 1
    assert sorted(groups[0]) == sorted(candidate.id for candidate in candidates[:5])
    assert candidates[5].id not in groups[0]
    # Detection wrote nothing: every status is unchanged.
    assert {candidate.id: candidate.status for candidate in service.list_candidates()} == before


def test_find_duplicate_groups_is_deterministic() -> None:
    class Row:
        def __init__(self, id_: str, statement: str) -> None:
            self.id = id_
            self.statement = statement

    rows = [Row(f"c{i}", statement) for i, statement in enumerate(PARAPHRASES)]
    first = find_duplicate_groups(rows)
    assert first == find_duplicate_groups(list(reversed(rows)))
    assert first == [sorted(row.id for row in rows)]


def test_merging_five_paraphrases_into_one_outcome_creates_no_second_outcome(
    service: ODIService,
) -> None:
    job_id, candidates = _seed(service, PARAPHRASES)
    target = _accepted_outcome(service, candidates[0].id)
    merged_ids = [candidate.id for candidate in candidates[1:]]

    outcome, evidence, merged = service.merge_candidates(target.id, merged_ids)

    assert outcome.id == target.id
    assert len(merged) == len(merged_ids)
    assert all(candidate.status is CandidateStatus.MERGED for candidate in merged)
    assert all(candidate.merged_into == target.id for candidate in merged)
    # Five evidence links on the one outcome: the acceptance write plus one per
    # merged paraphrase. Each is a distinct quote, not a copy of one quote.
    links = service.list_evidence(outcome_id=target.id)
    assert len(links) == 5
    assert len({link.content for link in links}) == 5
    assert len({link.raw["quote_id"] for link in links}) == 5
    absorbed = {
        link.raw.get("merged_from_candidate_id")
        for link in links
        if "merged_from_candidate_id" in link.raw
    }
    assert absorbed == set(merged_ids)
    assert len(service.get_outcomes(job_id)) == 1
    assert len(evidence) == len(merged_ids)


def test_repeated_merge_changes_nothing_and_duplicates_no_evidence(service: ODIService) -> None:
    _, candidates = _seed(service, PARAPHRASES)
    target = _accepted_outcome(service, candidates[0].id)
    merged_ids = [candidate.id for candidate in candidates[1:]]

    service.merge_candidates(target.id, merged_ids)
    after_first = len(service.list_evidence(outcome_id=target.id))

    outcome, evidence, merged = service.merge_candidates(target.id, merged_ids)

    assert outcome.id == target.id
    assert evidence == []
    assert merged == []
    assert len(service.list_evidence(outcome_id=target.id)) == after_first
    assert len(service.get_outcomes(target.job_id)) == 1


def test_merge_retains_originals_and_replays_to_the_same_state(tmp_path) -> None:

    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    service = ODIService(repo)
    _, candidates = _seed(service, PARAPHRASES)
    target = _accepted_outcome(service, candidates[0].id)
    merged_ids = [candidate.id for candidate in candidates[1:]]
    service.merge_candidates(target.id, merged_ids)
    repo.commit()

    repo.reload()
    assert len(service.get_outcomes(target.job_id)) == 1
    assert len(service.list_evidence(outcome_id=target.id)) == 5
    for candidate_id in merged_ids:
        stored = service.get_candidate(candidate_id)
        assert stored is not None
        assert stored.status is CandidateStatus.MERGED
        assert stored.merged_into == target.id
        # The source candidate and its quote are retained, not deleted.
        assert service.repo.get_quote(stored.quote_id) is not None

    # A fresh handle on the same file sees the same state.
    reopened = ODIService(SQLiteRepository(db))
    assert len(reopened.get_outcomes(target.job_id)) == 1
    assert len(reopened.list_evidence(outcome_id=target.id)) == 5
    for candidate_id in merged_ids:
        stored = reopened.get_candidate(candidate_id)
        assert stored is not None
        assert stored.status is CandidateStatus.MERGED
        assert stored.merged_into == target.id


def test_merging_an_accepted_source_is_refused_without_moving_anything(
    service: ODIService,
) -> None:
    _, candidates = _seed(service, PARAPHRASES)
    target = _accepted_outcome(service, candidates[0].id)
    other = _accepted_outcome(service, candidates[1].id)

    with pytest.raises(ValidationError):
        service.merge_candidates(target.id, [candidates[1].id])

    assert len(service.list_evidence(outcome_id=target.id)) == 1
    stored = service.get_candidate(candidates[1].id)
    assert stored is not None and stored.status is CandidateStatus.ACCEPTED
    assert other.id != target.id


def test_merging_a_rejected_source_is_refused(service: ODIService) -> None:
    _, candidates = _seed(service, PARAPHRASES)
    target = _accepted_outcome(service, candidates[0].id)
    service.reject_candidate(candidates[1].id, reason="Not a distinct need")

    with pytest.raises(ValidationError):
        service.merge_candidates(target.id, [candidates[1].id])

    assert len(service.list_evidence(outcome_id=target.id)) == 1


def test_merge_into_an_unknown_target_is_refused(service: ODIService) -> None:
    _, candidates = _seed(service, PARAPHRASES)

    with pytest.raises(OutcomeNotFoundError):
        service.merge_candidates("no-such-outcome", [candidates[0].id])

    stored = service.get_candidate(candidates[0].id)
    assert stored is not None and stored.status is CandidateStatus.PROPOSED


def test_merge_target_that_is_a_candidate_is_named_as_the_mistake(service: ODIService) -> None:
    _, candidates = _seed(service, PARAPHRASES)

    # Pointing the merge at a candidate instead of an outcome is the likely
    # mistake, so the message says so rather than "outcome not found".
    with pytest.raises(ValidationError, match="is not an accepted outcome"):
        service.merge_candidates(candidates[0].id, [candidates[1].id])


def test_merge_with_an_unknown_source_is_refused_without_partial_moves(
    service: ODIService,
) -> None:
    _, candidates = _seed(service, PARAPHRASES)
    target = _accepted_outcome(service, candidates[0].id)

    with pytest.raises(CandidateNotFoundError):
        service.merge_candidates(target.id, [candidates[1].id, "no-such-candidate"])

    # Validation happens before any write, so the valid source did not move.
    assert len(service.list_evidence(outcome_id=target.id)) == 1
    stored = service.get_candidate(candidates[1].id)
    assert stored is not None and stored.status is CandidateStatus.PROPOSED


def test_merging_a_source_already_merged_elsewhere_is_refused(service: ODIService) -> None:
    _, candidates = _seed(service, PARAPHRASES)
    target = _accepted_outcome(service, candidates[0].id)
    second = _accepted_outcome(service, candidates[1].id)
    service.merge_candidates(target.id, [candidates[2].id])

    with pytest.raises(ValidationError):
        service.merge_candidates(second.id, [candidates[2].id])

    stored = service.get_candidate(candidates[2].id)
    assert stored is not None and stored.merged_into == target.id


def test_failed_evidence_write_rolls_back_the_merge() -> None:
    repo = FailingEvidenceRepository()
    service = ODIService(repo)
    _, candidates = _seed(service, PARAPHRASES)
    target = _accepted_outcome(service, candidates[0].id)

    with pytest.raises(RuntimeError):
        service.merge_candidates(target.id, [candidate.id for candidate in candidates[1:]])

    for candidate in candidates[1:]:
        stored = service.get_candidate(candidate.id)
        assert stored is not None
        assert stored.status is CandidateStatus.PROPOSED
        assert stored.merged_into is None
