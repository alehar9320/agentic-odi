"""Tests for Stage 5: outcome-based segmentation."""

from __future__ import annotations

from agentic_odi_core import (
    Job,
    Outcome,
    Segment,
    SegmentVerdict,
    Step,
    compute_opportunity_score,
)
from agentic_odi_core.segmentation import (
    MIN_OUTCOMES_PER_SEGMENT,
    OutcomeClusterStrategy,
    segment_verdict,
    unclustered_outcomes,
)

_JOB_ID = "job-1"


def _outcome(
    statement: str,
    importance: float,
    satisfaction: float,
    step_id: str | None = None,
    outcome_id: str = "o",
    job_id: str = _JOB_ID,
) -> Outcome:
    return Outcome(
        id=outcome_id,
        job_id=job_id,
        step_id=step_id,
        statement=statement,
        importance=importance,
        satisfaction=satisfaction,
        opportunity_score=compute_opportunity_score(importance, satisfaction),
    )


def _job(name: str = "Rotate a leaked secret", job_id: str = _JOB_ID) -> Job:
    return Job(id=job_id, name=name, description="Rotate a leaked secret without an outage")


def _steps() -> list[Step]:
    return [
        Step(id="s1", job_id=_JOB_ID, name="Gather the current values", order=1),
        Step(id="s2", job_id=_JOB_ID, name="Verify the new value", order=2),
    ]


def _dump(segment: Segment) -> dict[str, object]:
    payload = segment.model_dump()
    payload.pop("created_at")
    return payload


# -- the verdict function ----------------------------------------------------


def test_underserved_needs_only_one_outcome_above_the_line() -> None:
    outcomes = [
        _outcome("Minimize the time to find the secret", 4, 4, outcome_id="a"),
        _outcome("Minimize the number of outages when rotating", 9, 3, outcome_id="b"),
    ]
    assert segment_verdict(outcomes) is SegmentVerdict.UNDERSERVED


def test_overserved_when_satisfaction_meets_importance_everywhere() -> None:
    outcomes = [
        _outcome("Minimize the number of clicks to rotate", 3, 9, outcome_id="a"),
        _outcome("Minimize the time to verify the new value", 5, 5, outcome_id="b"),
    ]
    assert segment_verdict(outcomes) is SegmentVerdict.OVERSERVED


def test_appropriately_served_when_scored_and_nothing_above_the_line() -> None:
    outcomes = [
        _outcome("Minimize the time to rotate the secret", 6, 4, outcome_id="a"),
        _outcome("Minimize the number of missed values", 5, 4, outcome_id="b"),
    ]
    assert segment_verdict(outcomes) is SegmentVerdict.APPROPRIATELY_SERVED


def test_an_unscored_outcome_is_reported_not_guessed() -> None:
    scored = _outcome("Minimize the time to rotate the secret", 6, 4, outcome_id="a")
    unscored = Outcome(id="u", job_id=_JOB_ID, statement="Minimize the time to rotate the secret")
    assert segment_verdict([scored]) is SegmentVerdict.APPROPRIATELY_SERVED
    assert segment_verdict([scored, unscored]) is None
    assert segment_verdict([]) is None


def test_the_underserved_threshold_is_the_shared_one_and_it_is_strict() -> None:
    exactly_ten = _outcome("Minimize the time to rotate", 10, 10, outcome_id="a")
    above_ten = _outcome("Minimize the time to rotate", 10, 9, outcome_id="b")
    assert exactly_ten.opportunity_score == 10.0
    assert segment_verdict([exactly_ten]) is not SegmentVerdict.UNDERSERVED
    assert segment_verdict([above_ten]) is SegmentVerdict.UNDERSERVED


# -- the default clustering strategy -----------------------------------------


def test_outcomes_cluster_by_job_and_step() -> None:
    jobs = [_job(), _job("Answer a security questionnaire", job_id="job-2")]
    outcomes = [
        _outcome("Minimize the time to find the secret", 9, 2, step_id="s1", outcome_id="a"),
        _outcome("Minimize the number of missed values", 8, 3, step_id="s1", outcome_id="b"),
        _outcome("Minimize the time to verify", 7, 2, step_id="s2", outcome_id="c"),
        _outcome("Minimize the time to verify", 7, 2, step_id="s2", outcome_id="d", job_id="job-2"),
        _outcome("Minimize the time to verify", 7, 2, step_id="s2", outcome_id="e", job_id="job-2"),
    ]
    segments = OutcomeClusterStrategy(steps=_steps(), people="Platform engineers").segment(
        jobs, outcomes
    )

    assert [(s.job_id, s.outcome_ids) for s in segments] == [
        ("job-1", ["a", "b"]),
        ("job-2", ["d", "e"]),
    ]
    assert [s.name for s in segments] == [
        "Platform engineers, Gather the current values",
        "Platform engineers, Answer a security questionnaire",
    ]
    assert segments[1].job_statement == "Rotate a leaked secret without an outage"


def test_a_cluster_needs_at_least_two_outcomes() -> None:
    assert MIN_OUTCOMES_PER_SEGMENT == 2
    jobs = [_job()]
    one = _outcome("Minimize the time to find the secret", 9, 2, step_id="s1", outcome_id="a")
    pair = _outcome("Minimize the missed values", 8, 3, step_id="s1", outcome_id="b")

    assert OutcomeClusterStrategy(steps=_steps()).segment(jobs, [one]) == []
    segments = OutcomeClusterStrategy(steps=_steps()).segment(jobs, [one, pair])
    assert len(segments) == 1


def test_a_single_outcome_is_reported_unclustered_not_dropped() -> None:
    jobs = [_job()]
    lone = _outcome("Minimize the time to find the secret", 9, 2, step_id="s1", outcome_id="a")
    first = _outcome("Minimize the number of missed values", 8, 3, step_id="s2", outcome_id="b")
    second = _outcome("Minimize the time to verify", 7, 2, step_id="s2", outcome_id="c")
    unattached = _outcome("Minimize the number of outages", 6, 2, outcome_id="d")
    outcomes = [lone, first, second, unattached]

    segments = OutcomeClusterStrategy(steps=_steps()).segment(jobs, outcomes)
    unclustered = unclustered_outcomes(segments, outcomes)

    assert [s.outcome_ids for s in segments] == [["b", "c"]]
    assert [outcome.id for outcome in unclustered] == ["a", "d"]


def test_the_run_is_deterministic_including_the_segment_id() -> None:
    jobs = [_job()]
    outcomes = [
        _outcome("Minimize the time to rotate the secret", 9, 2, step_id="s1", outcome_id="a"),
        _outcome("Minimize the number of missed values", 8, 3, step_id="s1", outcome_id="b"),
    ]
    strategy = OutcomeClusterStrategy(steps=_steps(), people="Platform engineers")

    first = strategy.segment(jobs, outcomes)
    second = strategy.segment(jobs, outcomes)

    assert [_dump(s) for s in first] == [_dump(s) for s in second]
    assert [s.id for s in first] == [s.id for s in second]


def test_evidence_added_to_a_cluster_updates_the_same_segment() -> None:
    jobs = [_job()]
    strategy = OutcomeClusterStrategy(steps=_steps())
    outcomes = [
        _outcome("Minimize the time to rotate the secret", 9, 2, step_id="s1", outcome_id="a"),
        _outcome("Minimize the number of missed values", 8, 3, step_id="s1", outcome_id="b"),
    ]
    more = _outcome("Minimize the time to confirm the value", 7, 2, step_id="s1", outcome_id="c")

    before = strategy.segment(jobs, outcomes)
    after = strategy.segment(jobs, [*outcomes, more])

    assert [s.id for s in before] == [s.id for s in after]
    assert after[0].confidence > before[0].confidence


def test_confidence_rises_with_evidence_and_stays_between_zero_and_one() -> None:
    jobs = [_job()]
    strategy = OutcomeClusterStrategy(steps=_steps())
    outcomes = [
        _outcome(
            f"Minimize the time to rotate the secret in stage {index}",
            9,
            2,
            step_id="s1",
            outcome_id=f"o{index}",
        )
        for index in range(6)
    ]

    segment = strategy.segment(jobs, outcomes)[0]

    assert 0.0 <= segment.confidence <= 1.0
    assert segment.confidence == 1.0


def test_the_rationale_names_the_outcomes_and_the_verdict() -> None:
    jobs = [_job()]
    outcomes = [
        _outcome("Minimize the time to rotate the secret", 9, 2, step_id="s1", outcome_id="a"),
        _outcome("Minimize the number of missed values", 8, 3, step_id="s1", outcome_id="b"),
    ]

    segment = OutcomeClusterStrategy(steps=_steps()).segment(jobs, outcomes)[0]

    assert "2 outcomes on Gather the current values" in segment.rationale
    assert "underserved" in segment.rationale
    assert "a=" in segment.rationale and "b=" in segment.rationale


# -- the methodology guardrail ----------------------------------------------


def test_segmentation_reads_no_demographic_attribute() -> None:
    """The segment's unit of analysis is the outcome, not the customer.

    Field names are asserted against an allowlist so a demographic field cannot
    quietly join the model.
    """
    demographics = ("age", "gender", "income", "industry", "size", "region", "role", "title")

    assert set(Segment.model_fields) == {
        "id",
        "job_id",
        "name",
        "people",
        "people_inferred",
        "job_statement",
        "outcome_ids",
        "verdict",
        "rationale",
        "confidence",
        "created_at",
    }
    assert not any(word in Segment.model_fields for word in demographics)


def test_the_output_is_invariant_to_demographic_wording() -> None:
    """Who the customer is changes nothing about which outcomes form a segment."""
    jobs = [_job()]
    steps = _steps()
    shared: list[tuple[str, float, float, str, str]] = [
        (
            "Minimize the time it takes to rotate the secret when it leaks in a hospital",
            9,
            2,
            "s1",
            "a",
        ),
        ("Minimize the number of missed values after rotation in a hospital", 8, 3, "s1", "b"),
        (
            "Minimize the time it takes to verify the new value in a hospital",
            7,
            2,
            "s2",
            "c",
        ),
        ("Minimize the number of outages when verifying in a hospital", 6, 2, "s2", "d"),
    ]
    steel_mill = [
        (statement.replace("hospital", "steel mill"), importance, satisfaction, step, oid)
        for statement, importance, satisfaction, step, oid in shared
    ]

    def build(rows: list[tuple[str, float, float, str, str]]) -> list[dict[str, object]]:
        outcomes = [
            _outcome(statement, importance, satisfaction, step_id=step, outcome_id=oid)
            for statement, importance, satisfaction, step, oid in rows
        ]
        strategy = OutcomeClusterStrategy(steps=steps, people="The people who rotate secrets")
        return [_dump(segment) for segment in strategy.segment(jobs, outcomes)]

    assert build(shared) == build(steel_mill)
