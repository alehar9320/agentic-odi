"""Pin the segment and strategy contract (D1/ALH-40 … D4/ALH-43).

Readiness choices pinned here, so no caller has to decide them again:

* **A segment is defined by stored members, never by demographics and never by
  a filter re-evaluated on read.** A hand-made segment and one accepted from a
  candidate differ only in ``origin``.
* **A cross-job or missing member is refused before any write.**
* **Deleting a segment leaves every outcome untouched.**
* **Suggestions persist nothing**; the same landscape yields the same candidates
  on every run, and acceptance creates exactly one segment.
* **The profile keeps the two halves separate** and reports zeroed keys, a
  ``None`` ratio (not ``0.0``) when nothing is measured, and a missing member.
* **Each strategy guardrail names the missing condition**, and ``new_market`` is
  refused while the alternatives evidence (M2-07/ALH-71) is absent rather than
  treating unchecked absence as proof.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.brief import BriefStrategy, render_brief
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import SegmentOrigin, StrategyKind
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.segmentation import (
    MIN_MEMBERS,
    importance_decile,
    suggest_segment_candidates,
)
from agentic_odi_core.services import (
    JobNotFoundError,
    ODIService,
    OutcomeNotFoundError,
    SegmentNotFoundError,
)

_STATEMENTS = (
    "Minimize the time it takes to publish a plugin when a release is ready",
    "Minimize the cost of supporting a plugin when it ships",
    "Minimize the time it takes to resolve a support ticket after a bug",
    "Minimize the time to roll back a bad plugin after a release",
    "Minimize the number of steps to install a plugin during setup",
)


def _statement(index: int) -> str:
    """A distinct, ODI-valid statement per index (the digit is a unit of measure)."""
    if index < len(_STATEMENTS):
        return _STATEMENTS[index]
    return f"Minimize the time it takes to publish plugin {index} when a release is ready"


@pytest.fixture()
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _job_with_outcomes(service: ODIService, scores: list[tuple[float, float]]):
    job = service.add_job("Publish a plugin")
    outcomes = [
        service.add_outcome(job.id, _statement(index), imp, sat)
        for index, (imp, sat) in enumerate(scores)
    ]
    return job, outcomes


# ----------------------------------------------------------------------- D1


def test_a_segment_stores_its_members_and_lists_them(service: ODIService) -> None:
    job, outcomes = _job_with_outcomes(service, [(9.0, 3.0), (8.0, 4.0), (7.0, 3.0)])
    segment = service.add_segment(
        job.id,
        "Release engineers",
        "They all own the publish step.",
        [outcome.id for outcome in outcomes],
    )
    assert segment.outcome_ids == [outcome.id for outcome in outcomes]
    listed = service.list_segments(job.id)
    assert [item.id for item in listed] == [segment.id]


def test_a_cross_job_member_is_refused_before_any_write(service: ODIService) -> None:
    job, outcomes = _job_with_outcomes(service, [(9.0, 3.0)])
    other_job = service.add_job("Other job")
    foreign = service.add_outcome(other_job.id, _STATEMENTS[1], 9.0, 2.0)

    with pytest.raises(ValidationError):
        service.add_segment(job.id, "Mixed", "spans jobs", [outcomes[0].id, foreign.id])
    assert service.list_segments(job.id) == []


def test_a_missing_member_is_refused_before_any_write(service: ODIService) -> None:
    job, outcomes = _job_with_outcomes(service, [(9.0, 3.0)])
    with pytest.raises(OutcomeNotFoundError):
        service.add_segment(job.id, "Ghost", "has a ghost", [outcomes[0].id, "does-not-exist"])
    assert service.list_segments(job.id) == []


def test_deleting_a_segment_leaves_outcomes_untouched(service: ODIService) -> None:
    job, outcomes = _job_with_outcomes(service, [(9.0, 3.0), (8.0, 4.0)])
    segment = service.add_segment(job.id, "Two", "just two", [o.id for o in outcomes])
    service.delete_segment(segment.id)
    assert service.get_segment(segment.id) is None
    for outcome in outcomes:
        assert service.get_outcome(outcome.id) is not None
    with pytest.raises(SegmentNotFoundError):
        service.segment_profile(segment.id)


def test_duplicate_member_ids_are_normalised(service: ODIService) -> None:
    job, outcomes = _job_with_outcomes(service, [(9.0, 3.0)])
    segment = service.add_segment(job.id, "Once", "same id twice", [outcomes[0].id] * 3)
    assert segment.outcome_ids == [outcomes[0].id]


# ----------------------------------------------------------------------- D2


def test_importance_decile_is_over_the_fixed_scale() -> None:
    assert importance_decile(None) is None
    assert importance_decile(1.0) == 1
    assert importance_decile(6.4) == 7
    assert importance_decile(10.0) == 10


def test_fewer_than_three_scored_outcomes_yields_none_plus_a_reason(
    service: ODIService,
) -> None:
    job, _ = _job_with_outcomes(service, [(9.0, 3.0), (8.0, 4.0)])
    result = service.suggest_segments(job.id)
    assert result.candidates == ()
    assert result.reason is not None and "scored outcomes" in result.reason


def test_a_landscape_yields_candidates_with_expected_membership(service: ODIService) -> None:
    job, outcomes = _job_with_outcomes(
        service,
        [(9.0, 3.0), (9.0, 2.0), (9.0, 4.0), (3.0, 9.0), (3.0, 9.0), (3.0, 9.0)],
    )
    result = service.suggest_segments(job.id)
    assert result.has_candidates
    underserved = [c for c in result.candidates if c.segment == "underserved"]
    assert len(underserved) == 1
    assert set(underserved[0].members) == {outcomes[0].id, outcomes[1].id, outcomes[2].id}
    assert underserved[0].evidence_count == 3


def test_identical_input_yields_identical_candidates(service: ODIService) -> None:
    job, _ = _job_with_outcomes(
        service, [(9.0, 3.0), (9.0, 2.0), (9.0, 4.0), (3.0, 9.0), (3.0, 9.0), (3.0, 9.0)]
    )
    first = service.suggest_segments(job.id)
    second = service.suggest_segments(job.id)
    assert [c.fingerprint for c in first.candidates] == [c.fingerprint for c in second.candidates]


def test_suggesting_persists_nothing(service: ODIService) -> None:
    job, _ = _job_with_outcomes(
        service, [(9.0, 3.0), (9.0, 2.0), (9.0, 4.0), (3.0, 9.0), (3.0, 9.0), (3.0, 9.0)]
    )
    service.suggest_segments(job.id)
    service.suggest_segments(job.id)
    assert service.list_segments(job.id) == []


def test_shuffled_equivalent_input_keeps_the_same_membership() -> None:
    from agentic_odi_core.models import Outcome

    def outcome(index: int, imp: float, sat: float) -> Outcome:
        return Outcome(
            id=f"00000000-0000-0000-0000-00000000000{index}",
            job_id="job",
            statement=_STATEMENTS[index],
            importance=imp,
            satisfaction=sat,
            opportunity_score=imp + max(imp - sat, 0.0),
        )

    forward = [outcome(0, 9.0, 3.0), outcome(1, 9.0, 2.0), outcome(2, 9.0, 4.0)]
    backward = list(reversed(forward))
    assert (
        suggest_segment_candidates(forward).candidates
        == suggest_segment_candidates(backward).candidates
    )


def test_exact_statement_dedupe_drops_a_repeat() -> None:
    from agentic_odi_core.models import Outcome

    def outcome(index: int, statement: str) -> Outcome:
        return Outcome(
            id=f"00000000-0000-0000-0000-00000000000{index}",
            job_id="job",
            statement=statement,
            importance=9.0,
            satisfaction=3.0,
            opportunity_score=15.0,
        )

    repeated = [outcome(0, _STATEMENTS[0]), outcome(1, _STATEMENTS[0]), outcome(2, _STATEMENTS[0])]
    assert suggest_segment_candidates(repeated).candidates == ()
    assert MIN_MEMBERS == 3


# --------------------------------------------------------------------- D2.2


def test_accepting_creates_exactly_one_segment(service: ODIService) -> None:
    job, outcomes = _job_with_outcomes(
        service, [(9.0, 3.0), (9.0, 2.0), (9.0, 4.0), (3.0, 9.0), (3.0, 9.0), (3.0, 9.0)]
    )
    candidate = service.suggest_segments(job.id).candidates[0]
    segment = service.accept_segment_candidate(job.id, candidate.fingerprint)
    assert segment.origin is SegmentOrigin.CANDIDATE
    assert segment.candidate_fingerprint == candidate.fingerprint
    assert set(segment.outcome_ids) == set(candidate.members)
    assert len(service.list_segments(job.id)) == 1


def test_repeat_acceptance_is_idempotent(service: ODIService) -> None:
    job, _ = _job_with_outcomes(
        service, [(9.0, 3.0), (9.0, 2.0), (9.0, 4.0), (3.0, 9.0), (3.0, 9.0), (3.0, 9.0)]
    )
    fingerprint = service.suggest_segments(job.id).candidates[0].fingerprint
    first = service.accept_segment_candidate(job.id, fingerprint)
    second = service.accept_segment_candidate(job.id, fingerprint)
    assert first.id == second.id
    assert len(service.list_segments(job.id)) == 1


def test_a_stale_fingerprint_is_refused(service: ODIService) -> None:
    job, _ = _job_with_outcomes(
        service, [(9.0, 3.0), (9.0, 2.0), (9.0, 4.0), (3.0, 9.0), (3.0, 9.0), (3.0, 9.0)]
    )
    with pytest.raises(ValidationError):
        service.accept_segment_candidate(job.id, "not-a-real-fingerprint")
    assert service.list_segments(job.id) == []


def test_manual_and_accepted_segments_differ_only_in_origin(service: ODIService) -> None:
    job, _ = _job_with_outcomes(
        service, [(9.0, 3.0), (9.0, 2.0), (9.0, 4.0), (3.0, 9.0), (3.0, 9.0), (3.0, 9.0)]
    )
    candidate = service.suggest_segments(job.id).candidates[0]
    accepted = service.accept_segment_candidate(job.id, candidate.fingerprint)
    manual = service.add_segment(
        job.id, accepted.name, accepted.criterion, list(accepted.outcome_ids)
    )
    assert accepted.origin is SegmentOrigin.CANDIDATE
    assert manual.origin is SegmentOrigin.MANUAL
    assert accepted.outcome_ids == manual.outcome_ids


# ----------------------------------------------------------------------- D3


def test_profile_counts_and_ratio_match_a_hand_computed_fixture(service: ODIService) -> None:
    # Scores: (9,3) → 15 underserved; (10,10) → 10 appropriate; (3,9) → 3 overserved.
    job, outcomes = _job_with_outcomes(service, [(9.0, 3.0), (10.0, 10.0), (3.0, 9.0)])
    segment = service.add_segment(job.id, "Three", "one of each", [o.id for o in outcomes])
    profile = service.segment_profile(segment.id)
    assert profile.total_members == 3
    assert profile.measured_count == 3
    assert profile.underserved_count == 1
    assert profile.appropriate_count == 1
    assert profile.overserved_count == 1
    assert profile.measured_ratio == pytest.approx(1.0)
    assert [entry.outcome_id for entry in profile.top_underserved] == [outcomes[0].id]
    assert [entry.outcome_id for entry in profile.top_overserved] == [outcomes[2].id]


def test_an_empty_segment_reports_zeroed_keys(service: ODIService) -> None:
    job, outcomes = _job_with_outcomes(service, [(9.0, 3.0)])
    segment = service.add_segment(job.id, "One", "single member", [outcomes[0].id])
    # Delete the member's job is too broad; instead simulate an empty segment by
    # deleting the only outcome, which leaves the stored membership dangling.
    service.delete_outcome(outcomes[0].id)
    profile = service.segment_profile(segment.id)
    assert profile.measured_count == 0
    assert profile.underserved_count == 0
    assert profile.top_underserved == ()
    assert profile.missing_count == 1
    assert any("no longer resolve" in gap for gap in profile.gaps)


def test_a_segment_with_no_measured_outcomes_has_a_none_ratio() -> None:
    from agentic_odi_core.models import Outcome, Segment
    from agentic_odi_core.segment_profile import build_segment_profile

    segment = Segment(job_id="job", name="Unscored", criterion="none measured", outcome_ids=["a"])
    member = Outcome(id="a", job_id="job", statement=_STATEMENTS[0])
    profile = build_segment_profile(segment, [member])
    assert profile.measured_count == 0
    assert profile.measured_ratio is None
    assert any("No member outcome is scored" in gap for gap in profile.gaps)


def test_an_unknown_segment_is_not_rendered_as_empty(service: ODIService) -> None:
    with pytest.raises(SegmentNotFoundError):
        service.segment_profile("nope")


# ----------------------------------------------------------------------- D4


def _underserved_segment(service: ODIService):
    job, outcomes = _job_with_outcomes(service, [(9.0, 3.0), (9.0, 2.0), (9.0, 4.0)])
    segment = service.add_segment(
        job.id, "Underserved", "all underserved", [o.id for o in outcomes]
    )
    return job, outcomes, segment


def test_differentiated_passes_with_an_underserved_member(service: ODIService) -> None:
    _, _, segment = _underserved_segment(service)
    strategy = service.choose_strategy(
        segment.id, StrategyKind.DIFFERENTIATED, "The gap is real.", "Better publish times."
    )
    assert strategy.kind is StrategyKind.DIFFERENTIATED


def test_differentiated_fails_without_an_underserved_member(service: ODIService) -> None:
    job, outcomes = _job_with_outcomes(service, [(3.0, 9.0), (3.0, 9.0), (3.0, 9.0)])
    segment = service.add_segment(job.id, "Overserved", "all overserved", [o.id for o in outcomes])
    with pytest.raises(ValidationError) as exc:
        service.choose_strategy(segment.id, "differentiated", "no", "no")
    assert "underserved" in str(exc.value)
    assert service.list_strategies(segment.id) == []


def test_disruptive_passes_with_an_overserved_member(service: ODIService) -> None:
    job, outcomes = _job_with_outcomes(service, [(3.0, 9.0), (3.0, 9.0), (3.0, 9.0)])
    segment = service.add_segment(job.id, "Overserved", "all overserved", [o.id for o in outcomes])
    strategy = service.choose_strategy(
        segment.id, "disruptive", "They are over-served.", "Cheaper option."
    )
    assert strategy.kind is StrategyKind.DISRUPTIVE


def test_disruptive_fails_without_an_overserved_member(service: ODIService) -> None:
    _, _, segment = _underserved_segment(service)
    with pytest.raises(ValidationError) as exc:
        service.choose_strategy(segment.id, "disruptive", "no", "no")
    assert "overserved" in str(exc.value)


def test_new_market_is_refused_while_alternatives_evidence_is_absent(
    service: ODIService,
) -> None:
    _, _, segment = _underserved_segment(service)
    with pytest.raises(ValidationError) as exc:
        service.choose_strategy(segment.id, "new_market", "nobody serves this", "New thing.")
    assert "alternatives" in str(exc.value).lower()


def test_an_unknown_strategy_kind_is_refused(service: ODIService) -> None:
    _, _, segment = _underserved_segment(service)
    with pytest.raises(ValidationError):
        service.choose_strategy(segment.id, "blue_ocean", "no", "no")


def test_a_strategy_without_a_segment_is_refused(service: ODIService) -> None:
    with pytest.raises(SegmentNotFoundError):
        service.choose_strategy("missing", "differentiated", "no", "no")


def test_a_strategy_appears_in_the_brief(service: ODIService) -> None:
    job, outcomes, segment = _underserved_segment(service)
    service.choose_strategy(
        segment.id, "differentiated", "The gap is real.", "Better publish times."
    )
    service.record_decision(
        job.id,
        [outcomes[0].id],
        rationale="Because the score is high.",
        decided_by="alex",
        decided_at="2026-01-02T00:00:00Z",
    )
    brief = service.build_brief(job.id, generated_at="2026-01-03T00:00:00Z")
    assert brief.strategy is not None
    rendered = render_brief(brief)
    assert "## The strategy" in rendered
    assert "differentiated" in rendered


def test_the_brief_omits_the_strategy_section_when_none_is_recorded(service: ODIService) -> None:
    job, _ = _job_with_outcomes(service, [(9.0, 3.0)])
    brief = service.build_brief(job.id, generated_at="2026-01-03T00:00:00Z")
    assert brief.strategy is None
    assert "## The strategy" not in render_brief(brief)


def test_unknown_job_is_refused_for_segments(service: ODIService) -> None:
    with pytest.raises(JobNotFoundError):
        service.add_segment("nope", "n", "c", ["x"])
    with pytest.raises(JobNotFoundError):
        service.suggest_segments("nope")


def test_brief_strategy_is_pure_input() -> None:
    from agentic_odi_core.brief import BriefInput

    brief = BriefInput(
        job_id="j",
        job_name="J",
        generated_at="2026-01-01T00:00:00Z",
        strategy=BriefStrategy(
            kind="differentiated",
            rationale="why",
            expected_effect="effect",
            segment_name="Segment",
        ),
    )
    assert "Segment" in render_brief(brief)


def test_the_shared_selector_picks_the_latest_strategy_on_an_overlapping_segment() -> None:
    """The CLI and the service must agree, so both call this one pure selector."""
    from agentic_odi_core.brief import (
        BriefSegment,
        BriefStrategyRecord,
        select_brief_strategy,
    )

    segments = [
        BriefSegment(segment_id="s1", name="Release engineers", outcome_ids=("o1", "o2")),
        BriefSegment(segment_id="s2", name="Support", outcome_ids=("o9",)),
    ]
    strategies = [
        BriefStrategyRecord("st1", "s1", "2026-01-01T00:00:00Z", "differentiated", "old", "e"),
        BriefStrategyRecord("st2", "s1", "2026-02-01T00:00:00Z", "disruptive", "new", "e"),
        BriefStrategyRecord("st9", "s2", "2026-03-01T00:00:00Z", "differentiated", "other", "e"),
    ]

    chosen = select_brief_strategy(["o2"], segments, strategies)

    assert chosen is not None
    assert chosen.kind == "disruptive"
    assert chosen.rationale == "new"
    assert chosen.segment_name == "Release engineers"


def test_the_shared_selector_returns_none_when_no_segment_overlaps() -> None:
    from agentic_odi_core.brief import (
        BriefSegment,
        BriefStrategyRecord,
        select_brief_strategy,
    )

    segments = [BriefSegment(segment_id="s1", name="Release engineers", outcome_ids=("o1",))]
    strategies = [
        BriefStrategyRecord("st1", "s1", "2026-01-01T00:00:00Z", "differentiated", "why", "e")
    ]

    assert select_brief_strategy(["o-unrelated"], segments, strategies) is None
    assert select_brief_strategy([], segments, strategies) is None
