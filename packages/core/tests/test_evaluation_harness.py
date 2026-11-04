"""The evaluation harness: a service is judged by the shared fixture.

A service that scores its outcomes through ``compute_opportunity_score`` passes
the harness. A service that computes its own arithmetic fails, and the failure
names the outcome id and both values — the score the fixture's arithmetic
expects, and the score the service reported.

Every expected value here is read from the fixture; none is re-derived.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.evaluation import (
    OutcomeScoreMismatchError,
    assert_outcome_scores_match,
    fixture_expected_scores,
    load_score_fixture,
)
from agentic_odi_core.models import Outcome, compute_opportunity_score
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService

STATEMENT = "Minimize the time it takes to onboard a customer when they sign up"

#: A scored pair that appears in the fixture, so its expected value is the
#: fixture's own number rather than a literal repeated here.
_IMPORTANCE, _SATISFACTION = 8.0, 4.0


def _fixture_score(importance: float, satisfaction: float) -> float:
    return fixture_expected_scores(load_score_fixture())[(importance, satisfaction)]


def _outcome(
    outcome_id: str,
    job_id: str,
    importance: float | None,
    satisfaction: float | None,
    opportunity_score: float | None,
) -> Outcome:
    return Outcome(
        id=outcome_id,
        job_id=job_id,
        statement=STATEMENT,
        importance=importance,
        satisfaction=satisfaction,
        opportunity_score=opportunity_score,
    )


def test_a_service_that_uses_the_shared_function_passes() -> None:
    """ODIService scores through the shared function, so its outcomes clear the harness."""
    service = ODIService(InMemoryRepository())
    job = service.add_job("Onboard customers")
    service.add_outcome(job.id, STATEMENT, importance=_IMPORTANCE, satisfaction=_SATISFACTION)

    assert_outcome_scores_match(service.get_outcomes(job.id))


def test_a_service_that_computes_its_own_score_fails_named() -> None:
    """A service reporting its own arithmetic fails, naming the id and both values."""
    service = ODIService(InMemoryRepository())
    job = service.add_job("Onboard customers")
    expected = _fixture_score(_IMPORTANCE, _SATISFACTION)
    wrong = expected + 1.0
    service.repo.add_outcome(_outcome("O-self-computed", job.id, _IMPORTANCE, _SATISFACTION, wrong))

    with pytest.raises(OutcomeScoreMismatchError) as raised:
        assert_outcome_scores_match(service.get_outcomes(job.id))

    message = str(raised.value)
    assert "O-self-computed" in message
    assert str(wrong) in message
    assert str(expected) in message
    assert raised.value.expected == expected
    assert raised.value.reported == wrong


def test_a_wrong_score_is_caught_when_the_fixture_is_supplied() -> None:
    """The harness reads the supplied fixture; it does not re-derive the number."""
    fixture = load_score_fixture()
    expected = fixture_expected_scores(fixture)[(_IMPORTANCE, _SATISFACTION)]
    wrong = _outcome("O-fixture", "job-1", _IMPORTANCE, _SATISFACTION, expected + 0.5)

    with pytest.raises(OutcomeScoreMismatchError) as raised:
        assert_outcome_scores_match([wrong], fixture)

    assert raised.value.expected == expected
    assert raised.value.reported == expected + 0.5


def test_a_pair_outside_the_fixture_is_judged_by_the_shared_function() -> None:
    """The harness checks the arithmetic generally, not only the fixture's cases."""
    # (6.0, 2.0) is not a fixture case, so the shared function supplies the number.
    wrong = _outcome("O-off-fixture", "job-1", 6.0, 2.0, compute_opportunity_score(6.0, 2.0) + 0.5)

    with pytest.raises(OutcomeScoreMismatchError) as raised:
        assert_outcome_scores_match([wrong])

    assert raised.value.expected == compute_opportunity_score(6.0, 2.0)


def test_an_unscored_outcome_is_allowed() -> None:
    """An outcome with no score is a legal record; the harness must not raise."""
    service = ODIService(InMemoryRepository())
    job = service.add_job("Onboard customers")
    service.add_outcome(job.id, STATEMENT, importance=None, satisfaction=None)

    assert_outcome_scores_match(service.get_outcomes(job.id))


def test_an_unscored_outcome_alongside_a_scored_one_still_passes() -> None:
    """A missing score is skipped, not compared, and does not stop the scan."""
    expected = _fixture_score(_IMPORTANCE, _SATISFACTION)
    scored = _outcome("O-scored", "job-1", _IMPORTANCE, _SATISFACTION, expected)
    unscored = _outcome("O-unscored", "job-1", None, None, None)

    assert_outcome_scores_match([unscored, scored])


def test_the_shared_function_agrees_with_every_scored_fixture_case() -> None:
    """The scorer and the fixture cannot drift: each scored case matches the function."""
    for case in load_score_fixture()["cases"]:
        if case["importance"] is None or case["satisfaction"] is None:
            assert case["score"] is None
            continue
        assert compute_opportunity_score(case["importance"], case["satisfaction"]) == case["score"]
