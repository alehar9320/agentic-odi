"""Pin what an opportunity is worth (W1/ALH-64).

Readiness choices pinned here:

* A value estimate is a **recorded judgement**, never derived from the
  opportunity score. Two outcomes with the same score and different estimates
  keep different estimates; the score is not read.
* A missing estimate is ``unsized`` and renders ``not measured``, never ``0``.
  A real ``0`` estimate is a real value and is kept.
* A ``market`` or ``pilot`` basis requires a named ``value_source``; an
  ``estimate`` basis may have one but does not need it.
* The unit is part of the claim: clearing the estimate clears the unit, basis,
  sample, and source together, so no companion describes a number that is gone.
* The estimate is never summed across outcomes: overlapping estimates would
  double-count and nothing would flag it.
"""

from __future__ import annotations

import pytest
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.evaluation import classify_value
from agentic_odi_core.models import Outcome
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService, OutcomeNotFoundError
from pydantic import ValidationError as ModelValidationError

_STATEMENT = "Minimize the time it takes to publish a plugin when a release is ready"
_OTHER_STATEMENT = "Minimize the cost of supporting a plugin when it ships"


@pytest.fixture()
def service() -> ODIService:
    return ODIService(InMemoryRepository())


def _outcome(**overrides) -> Outcome:
    base = {"job_id": "job-1", "statement": _STATEMENT, "importance": 9.0, "satisfaction": 3.0}
    base.update(overrides)
    return Outcome(**base)


# ------------------------------------------------------------------ classification


def test_no_estimate_is_unsized_not_zero():
    assert classify_value(_outcome()) == "unsized"
    assert classify_value(_outcome(value_estimate=None)) == "unsized"


def test_a_lone_judgement_is_thin():
    assert classify_value(_outcome(value_estimate=250_000.0, value_unit="currency")) == "thin"
    # An explicit sample of one is still one person's guess.
    assert (
        classify_value(_outcome(value_estimate=250_000.0, value_unit="currency", value_n=1))
        == "thin"
    )


def test_a_market_basis_is_sized():
    sized = _outcome(
        value_estimate=250_000.0,
        value_unit="currency",
        value_basis="market",
        value_source="Gartner 2025 plugin market report",
    )
    assert classify_value(sized) == "sized"


def test_a_pilot_basis_is_sized():
    sized = _outcome(
        value_estimate=400.0,
        value_unit="hours",
        value_basis="pilot",
        value_source="3-week beta with 6 admins",
    )
    assert classify_value(sized) == "sized"


def test_a_sample_of_more_than_one_is_sized_even_on_an_estimate_basis():
    assert classify_value(_outcome(value_estimate=100.0, value_unit="users", value_n=12)) == "sized"


def test_a_real_zero_estimate_is_sized_when_the_basis_supports_it():
    zero = _outcome(
        value_estimate=0.0,
        value_unit="currency",
        value_basis="market",
        value_source="No buyers in the segment",
    )
    assert classify_value(zero) == "sized"


# ------------------------------------------------------------------ the model rules


def test_a_market_basis_without_a_source_is_refused():
    with pytest.raises(ModelValidationError, match="requires a value_source"):
        _outcome(value_estimate=1.0, value_unit="currency", value_basis="market")


def test_a_pilot_basis_without_a_source_is_refused():
    with pytest.raises(ModelValidationError, match="requires a value_source"):
        _outcome(value_estimate=1.0, value_unit="currency", value_basis="pilot")


def test_a_blank_source_does_not_count_as_a_source():
    with pytest.raises(ModelValidationError, match="requires a value_source"):
        _outcome(
            value_estimate=1.0,
            value_unit="currency",
            value_basis="pilot",
            value_source="   ",
        )


def test_an_estimate_basis_needs_no_source():
    plain = _outcome(value_estimate=10.0, value_unit="users")
    assert plain.value_basis == "estimate"
    assert plain.value_source is None


def test_a_negative_estimate_is_refused_by_the_model():
    with pytest.raises(ModelValidationError):
        _outcome(value_estimate=-1.0, value_unit="currency")


def test_an_unknown_unit_is_refused():
    with pytest.raises(ModelValidationError):
        _outcome(value_estimate=1.0, value_unit="dollars")


# ------------------------------------------------------------------ the service


def test_set_outcome_value_stores_what_the_caller_supplied(service: ODIService):
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0)
    updated = service.set_outcome_value(
        outcome.id,
        250_000.0,
        unit="currency",
        basis="market",
        source="Gartner 2025 plugin market report",
    )
    assert updated.value_estimate == 250_000.0
    assert updated.value_unit == "currency"
    assert updated.value_basis == "market"
    assert updated.value_source == "Gartner 2025 plugin market report"
    assert classify_value(updated) == "sized"


def test_the_value_is_never_derived_from_the_score(service: ODIService):
    job = service.add_job("Publish a plugin")
    # Two outcomes with identical scores must keep independent estimates: a
    # derived value would make these equal.
    a = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0)
    b = service.add_outcome(job.id, _OTHER_STATEMENT, 9.0, 3.0)
    assert a.opportunity_score == b.opportunity_score
    service.set_outcome_value(a.id, 100.0, unit="users")
    service.set_outcome_value(b.id, 900.0, unit="users")
    stored_a = service.repo.get_outcome(a.id)
    stored_b = service.repo.get_outcome(b.id)
    assert stored_a is not None and stored_a.value_estimate == 100.0
    assert stored_b is not None and stored_b.value_estimate == 900.0


def test_setting_a_value_leaves_the_score_untouched(service: ODIService):
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0)
    before = outcome.opportunity_score
    updated = service.set_outcome_value(outcome.id, 5.0, unit="users")
    assert updated.opportunity_score == before


def test_a_market_basis_without_a_source_is_refused_by_the_service(service: ODIService):
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0)
    with pytest.raises(ValidationError, match="requires a value_source"):
        service.set_outcome_value(outcome.id, 1.0, unit="currency", basis="market")
    # Nothing was written: the outcome still has no estimate.
    stored = service.repo.get_outcome(outcome.id)
    assert stored is not None and stored.value_estimate is None


def test_an_estimate_without_a_unit_is_refused(service: ODIService):
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0)
    with pytest.raises(ValidationError, match="needs a unit"):
        service.set_outcome_value(outcome.id, 100.0)


def test_clearing_the_estimate_clears_its_companions(service: ODIService):
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0)
    service.set_outcome_value(
        outcome.id, 100.0, unit="currency", basis="pilot", n=4, source="beta cohort"
    )
    cleared = service.set_outcome_value(outcome.id, None)
    assert cleared.value_estimate is None
    assert cleared.value_unit is None
    assert cleared.value_basis == "estimate"
    assert cleared.value_n is None
    assert cleared.value_source is None
    assert classify_value(cleared) == "unsized"


def test_an_unknown_outcome_is_refused(service: ODIService):
    with pytest.raises(OutcomeNotFoundError):
        service.set_outcome_value("nope", 1.0, unit="currency")


def test_a_blank_source_is_refused_by_the_service(service: ODIService):
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0)
    with pytest.raises(ValidationError, match="must not be blank"):
        service.set_outcome_value(outcome.id, 1.0, unit="currency", source="   ")


# ------------------------------------------------------------------ persistence


def test_a_value_survives_sqlite_replay(tmp_path) -> None:
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    path = str(tmp_path / "value.db")
    repo = SQLiteRepository(db_path=path)
    service = ODIService(repo)
    job = service.add_job("Publish a plugin")
    outcome = service.add_outcome(job.id, _STATEMENT, 9.0, 3.0, at="2026-01-01T00:00:00Z")
    service.set_outcome_value(
        outcome.id,
        250_000.0,
        unit="currency",
        basis="market",
        source="Gartner 2025 plugin market report",
    )
    repo.commit()
    repo.close()

    replay = ODIService(SQLiteRepository(db_path=path))
    reread = replay.repo.get_outcome(outcome.id)
    assert reread is not None
    assert reread.value_estimate == 250_000.0
    assert reread.value_unit == "currency"
    assert reread.value_basis == "market"
    assert reread.value_source == "Gartner 2025 plugin market report"
    replay.repo.close()
