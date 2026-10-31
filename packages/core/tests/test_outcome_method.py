"""Sample size and method travel with an outcome score."""

from __future__ import annotations

import pytest
from agentic_odi_core.models import Outcome
from pydantic import ValidationError

_STATEMENT = "Minimize the time it takes to onboard a new engineer."


def _outcome(**overrides: object) -> Outcome:
    base: dict[str, object] = {
        "job_id": "job-1",
        "statement": _STATEMENT,
        "importance": 8.0,
        "satisfaction": 6.0,
    }
    base.update(overrides)
    return Outcome(**base)


def test_counts_default_to_none_not_zero_or_one() -> None:
    outcome = _outcome()
    assert outcome.importance_n is None
    assert outcome.satisfaction_n is None
    assert outcome.score_method == "estimate"


def test_a_count_of_zero_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _outcome(importance_n=0)


def test_a_negative_count_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _outcome(satisfaction_n=-3)


def test_a_non_integer_count_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _outcome(importance_n=1.5)


def test_a_count_above_one_requires_a_non_estimate_method() -> None:
    with pytest.raises(ValidationError):
        _outcome(importance_n=40, score_method="estimate")


def test_a_survey_with_a_count_is_accepted() -> None:
    outcome = _outcome(importance_n=40, satisfaction_n=40, score_method="survey")
    assert outcome.score_method == "survey"
    assert outcome.importance_n == 40


def test_an_estimate_with_unknown_counts_is_accepted() -> None:
    outcome = _outcome(score_method="estimate")
    assert outcome.importance_n is None


def test_an_import_with_a_count_is_accepted() -> None:
    outcome = _outcome(satisfaction_n=12, score_method="import")
    assert outcome.satisfaction_n == 12
