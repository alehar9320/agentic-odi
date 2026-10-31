"""The trust surfaces behave per their named provisional conventions.

These surfaces were originally seams that refused until a decision was approved.
They now run against a documented provisional convention, so the tests pin the
*behaviour* the product depends on and the *refusals* that remain: a surface
whose inputs are absent (no sample, no baseline) still raises rather than
inventing a band, class or direction.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.errors import OdiError, ValidationError
from agentic_odi_core.models import Outcome, ScoreSnapshot
from agentic_odi_core.trust import (
    BootstrapConvention,
    IntervalProvenancePolicy,
    RetentionPolicy,
    TrustContractPendingError,
    classify_confidence,
    opportunity_delta_from_scores,
    opportunity_interval,
    outcome_delta,
    persisted_interval,
    rank_outcomes_honestly,
    retain_survey_inputs,
    retained_survey_inputs,
)

_STATEMENT = "Minimize the time it takes to onboard a new engineer when they join."


def _outcome(**overrides: object) -> Outcome:
    base: dict[str, object] = {
        "job_id": "job-1",
        "statement": _STATEMENT,
        "importance": 8.0,
        "satisfaction": 6.0,
        "opportunity_score": 10.0,
    }
    base.update(overrides)
    return Outcome(**base)


def test_pending_error_is_an_odi_error_and_names_the_gate() -> None:
    err = TrustContractPendingError("opportunity_interval", BootstrapConvention)

    assert isinstance(err, OdiError)
    assert err.capability == "opportunity_interval"
    assert err.decision == BootstrapConvention
    assert "opportunity_interval" in str(err)
    assert BootstrapConvention in str(err)


# --- B3: a band, not a point -------------------------------------------------


def test_an_estimate_gets_a_no_band_placeholder() -> None:
    interval = opportunity_interval(_outcome(score_method="estimate"))

    assert interval.estimate is True
    assert interval.low == interval.high == 10.0


def test_an_outcome_with_no_score_refuses_a_band() -> None:
    with pytest.raises(TrustContractPendingError) as caught:
        opportunity_interval(_outcome(opportunity_score=None, importance=None, satisfaction=None))

    assert caught.value.decision == BootstrapConvention


def test_a_survey_band_is_deterministic_and_not_an_estimate() -> None:
    outcome = _outcome(score_method="survey", importance_n=40, satisfaction_n=40)

    first = opportunity_interval(outcome)
    second = opportunity_interval(outcome)

    assert first == second
    assert first.estimate is False
    assert first.low <= first.high


# --- B4.1: measured / thin / none -------------------------------------------


def test_a_large_survey_is_measured() -> None:
    outcome = _outcome(score_method="survey", importance_n=40, satisfaction_n=40)

    assert classify_confidence(outcome) == "measured"


def test_a_small_survey_is_thin() -> None:
    outcome = _outcome(score_method="survey", importance_n=3, satisfaction_n=3)

    assert classify_confidence(outcome) == "thin"


def test_a_survey_label_alone_is_not_evidence() -> None:
    # A survey method with no count is unknown, not measured.
    assert classify_confidence(_outcome(score_method="survey")) == "none"


def test_an_estimate_is_none_and_an_unscored_outcome_is_none() -> None:
    assert classify_confidence(_outcome(score_method="estimate")) == "none"
    assert classify_confidence(_outcome(opportunity_score=None)) == "none"


def test_the_weakest_dimension_bounds_the_class() -> None:
    outcome = _outcome(score_method="survey", importance_n=40, satisfaction_n=2)

    assert classify_confidence(outcome) == "thin"


# --- B4: honest ranking ------------------------------------------------------


def test_an_estimate_of_twelve_ranks_below_a_survey_of_nine_point_five() -> None:
    thin = _outcome(id="thin", opportunity_score=12.0, score_method="estimate")
    measured = _outcome(
        id="measured",
        opportunity_score=9.5,
        score_method="survey",
        importance_n=40,
        satisfaction_n=40,
        opportunity_low=8.5,
        opportunity_high=10.5,
    )

    ranked = rank_outcomes_honestly([thin, measured])

    assert [o.id for o in ranked] == ["measured", "thin"]


def test_ranking_keeps_measured_thin_and_none_in_separate_groups() -> None:
    measured = _outcome(id="m", score_method="survey", importance_n=40, satisfaction_n=40)
    thin = _outcome(id="t", score_method="survey", importance_n=2, satisfaction_n=2)
    none = _outcome(id="n", score_method="estimate")
    unscored = _outcome(id="u", opportunity_score=None, importance=None, satisfaction=None)

    ranked = rank_outcomes_honestly([none, unscored, thin, measured])

    assert [o.id for o in ranked] == ["m", "t", "n", "u"]


def test_ranking_is_stable_for_ties_by_id() -> None:
    a = _outcome(id="a", score_method="survey", importance_n=40, satisfaction_n=40)
    b = _outcome(id="b", score_method="survey", importance_n=40, satisfaction_n=40)

    assert [o.id for o in rank_outcomes_honestly([b, a])] == ["a", "b"]


# --- B3.1: retention stub ----------------------------------------------------


def test_retain_survey_inputs_keeps_inputs_without_deleting() -> None:
    from agentic_odi_core.trust import RetainedSurveyInput

    item = RetainedSurveyInput(
        outcome_id="o-1", respondent_id="r-1", importance=8.0, satisfaction=6.0
    )

    retain_survey_inputs([item])
    retain_survey_inputs([item])  # a repeat does not duplicate

    assert retained_survey_inputs("o-1") == [item]


def test_retained_survey_inputs_refuses_when_nothing_was_retained() -> None:
    # An empty list would read as "zero responses" and let a caller bootstrap
    # from no data; the read side must name the unapproved retention decision.
    with pytest.raises(TrustContractPendingError) as caught:
        retained_survey_inputs("never-imported")

    assert caught.value.decision == RetentionPolicy
    assert caught.value.capability == "retained_survey_inputs"


# --- B3.2: persisted interval provenance -------------------------------------


def test_a_stored_band_reads_back_with_its_provenance() -> None:
    outcome = _outcome(
        score_method="survey",
        importance_n=40,
        satisfaction_n=40,
        opportunity_low=8.5,
        opportunity_high=10.5,
        interval_n=40,
        interval_seed=0,
        interval_confidence_level=0.95,
        interval_computed_at="2026-01-01T00:00:00+00:00",
    )

    provenance = persisted_interval(outcome, [])

    assert provenance.low == 8.5
    assert provenance.high == 10.5
    assert provenance.n == 40
    assert provenance.stale is False


def test_a_band_is_stale_when_a_later_snapshot_moved_the_score() -> None:
    outcome = _outcome(opportunity_low=8.5, opportunity_high=10.5, opportunity_score=10.0)
    history = [ScoreSnapshot(outcome_id=outcome.id, opportunity_score=12.0)]

    provenance = persisted_interval(outcome, history)

    assert provenance.stale is True


def test_an_outcome_with_no_band_refuses_provenance() -> None:
    with pytest.raises(TrustContractPendingError) as caught:
        persisted_interval(_outcome(), [])

    assert caught.value.decision == IntervalProvenancePolicy


# --- B6.1: signed deltas -----------------------------------------------------


def _snapshot(**overrides: object) -> ScoreSnapshot:
    base: dict[str, object] = {
        "outcome_id": "o-1",
        "importance": 8.0,
        "satisfaction": 6.0,
        "opportunity_score": 10.0,
    }
    base.update(overrides)
    return ScoreSnapshot(**base)


def test_a_rise_is_signed_up_and_the_deltas_are_the_differences() -> None:
    history = [
        _snapshot(at="2026-01-01T00:00:00+00:00"),
        _snapshot(
            at="2026-01-02T00:00:00+00:00",
            importance=9.0,
            satisfaction=6.0,
            opportunity_score=12.0,
        ),
    ]

    delta = outcome_delta(history)

    assert delta.importance == 1.0
    assert delta.satisfaction == 0.0
    assert delta.opportunity == 2.0
    assert delta.direction == "up"


def test_a_fall_is_signed_down() -> None:
    history = [
        _snapshot(at="2026-01-01T00:00:00+00:00", opportunity_score=12.0),
        _snapshot(at="2026-01-02T00:00:00+00:00", opportunity_score=10.0),
    ]

    delta = outcome_delta(history)

    assert delta.opportunity == -2.0
    assert delta.direction == "down"


def test_an_unchanged_score_is_flat() -> None:
    history = [
        _snapshot(at="2026-01-01T00:00:00+00:00"),
        _snapshot(at="2026-01-02T00:00:00+00:00"),
    ]

    delta = outcome_delta(history)

    assert delta.opportunity == 0.0
    assert delta.direction == "flat"


def test_a_missing_dimension_yields_none_not_zero() -> None:
    history = [
        _snapshot(at="2026-01-01T00:00:00+00:00", importance=None, satisfaction=None),
        _snapshot(at="2026-01-02T00:00:00+00:00"),
    ]

    delta = outcome_delta(history)

    assert delta.importance is None
    assert delta.satisfaction is None


def test_since_selects_the_baseline_and_a_pre_history_since_fails() -> None:
    history = [
        _snapshot(at="2026-01-01T00:00:00+00:00", opportunity_score=10.0),
        _snapshot(at="2026-01-02T00:00:00+00:00", opportunity_score=11.0),
        _snapshot(at="2026-01-03T00:00:00+00:00", opportunity_score=12.0),
    ]

    delta = outcome_delta(history, since="2026-01-02T00:00:00+00:00")
    assert delta.opportunity == 1.0  # from the 11.0 baseline

    with pytest.raises(ValidationError):
        outcome_delta(history, since="2025-12-31T00:00:00+00:00")


def test_an_empty_history_has_no_baseline() -> None:
    with pytest.raises(ValidationError):
        outcome_delta([])


def test_delta_direction_helper_agrees_with_the_snapshot_path() -> None:
    assert opportunity_delta_from_scores(10.0, 12.0) == (2.0, "up")
    assert opportunity_delta_from_scores(12.0, 10.0) == (-2.0, "down")
    assert opportunity_delta_from_scores(10.0, 10.0) == (0.0, "flat")
    assert opportunity_delta_from_scores(None, 10.0) == (None, "flat")


def test_the_surfaces_are_exported_from_the_package_root() -> None:
    import agentic_odi_core as core

    for name in (
        "OpportunityInterval",
        "OutcomeDelta",
        "SurveyAggregate",
        "RetainedSurveyInput",
        "IntervalProvenance",
        "TrustContractPendingError",
        "opportunity_interval",
        "classify_confidence",
        "outcome_delta",
        "parse_survey",
        "aggregate_survey",
        "retain_survey_inputs",
        "retained_survey_inputs",
        "persisted_interval",
        "rank_outcomes_honestly",
    ):
        assert name in core.__all__
        assert hasattr(core, name)
