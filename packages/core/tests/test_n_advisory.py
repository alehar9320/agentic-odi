"""The minimum-n advisory warns about a thin sample without overclaiming (M2-14).

The advisory is a product warning line, not a validity certificate: it names the
recorded sample and the threshold and says "below advisory threshold", never that
a sample below it is worthless or that one above it is reliable. These tests pin
the boundary (strictly below 20), the dimension that triggered it, and the cases
that must produce *no* advisory rather than a fabricated ``n=0``.
"""

from __future__ import annotations

from agentic_odi_core.evaluation import MIN_MEANINGFUL_N, n_advisory
from agentic_odi_core.models import Outcome

_STATEMENT = "Minimize the time it takes to onboard a new engineer when they join."


def _outcome(**overrides: object) -> Outcome:
    base: dict[str, object] = {
        "job_id": "job-1",
        "statement": _STATEMENT,
        "importance": 8.0,
        "satisfaction": 6.0,
        "opportunity_score": 10.0,
        "score_method": "survey",
    }
    base.update(overrides)
    return Outcome(**base)


def test_the_threshold_is_the_documented_twenty() -> None:
    assert MIN_MEANINGFUL_N == 20


def test_a_four_response_sample_is_advised_with_its_number_and_threshold() -> None:
    advisory = n_advisory(_outcome(importance_n=4, satisfaction_n=4))

    assert advisory is not None
    assert advisory.n == 4
    assert advisory.threshold == 20
    assert advisory.method == "survey"
    assert advisory.dimension == "both"
    assert "4" in advisory.message
    assert "20" in advisory.message
    assert "below the advisory threshold" in advisory.message
    # It must not promise statistical validity on either side of the line.
    assert "significant" not in advisory.message
    assert "invalid" not in advisory.message


def test_a_twenty_five_response_sample_is_not_advised() -> None:
    assert n_advisory(_outcome(importance_n=25, satisfaction_n=25)) is None


def test_the_boundary_is_strictly_below_twenty() -> None:
    assert n_advisory(_outcome(importance_n=19, satisfaction_n=19)) is not None
    assert n_advisory(_outcome(importance_n=20, satisfaction_n=20)) is None
    assert n_advisory(_outcome(importance_n=21, satisfaction_n=21)) is None


def test_the_smaller_dimension_triggers_and_is_named() -> None:
    advisory = n_advisory(_outcome(importance_n=40, satisfaction_n=12))

    assert advisory is not None
    assert advisory.n == 12
    assert advisory.dimension == "satisfaction"
    assert "satisfaction" in advisory.message


def test_unequal_but_both_below_names_both() -> None:
    advisory = n_advisory(_outcome(importance_n=12, satisfaction_n=12))

    assert advisory is not None
    assert advisory.dimension == "both"


def test_an_estimate_is_not_advised_rather_than_advised_at_zero() -> None:
    # An estimate has no sample; inventing n=0 would turn an unknown into a fact.
    assert n_advisory(_outcome(score_method="estimate")) is None


def test_an_unknown_count_is_not_advised() -> None:
    assert n_advisory(_outcome(importance_n=None, satisfaction_n=None)) is None


def test_a_partial_count_advises_on_the_known_dimension_only() -> None:
    advisory = n_advisory(_outcome(importance_n=8, satisfaction_n=None))

    assert advisory is not None
    assert advisory.n == 8
    assert advisory.dimension == "importance"


def test_an_unscored_outcome_is_not_advised() -> None:
    assert n_advisory(_outcome(opportunity_score=None, importance_n=3, satisfaction_n=3)) is None


def test_the_advisory_is_exported_from_the_package_root() -> None:
    import agentic_odi_core as core

    assert core.MIN_MEANINGFUL_N == 20
    assert "n_advisory" in core.__all__
    assert "Advisory" in core.__all__
