"""Writing an outcome's V2MOM links at creation and update time (#590).

An outcome says which objective it advances, and the link is validated against
the vision the store holds *now*. ``add_outcome``/``update_outcome`` accept the
links directly so a caller does not have to create the outcome and then call
``link_outcome`` — but the same refusal applies: an unknown objective is named,
never guessed, and an unlinked outcome stays legal.
"""

from __future__ import annotations

import pytest
from agentic_odi_core import ODIService
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import V2MOM, Job
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.traceability import objective_key

_METHOD = "Cut time-to-first-value"
_MEASURE = "Net revenue retention above 120%"
_STATEMENT = "Minimize the time it takes to onboard a new engineer when they join"


def _service() -> ODIService:
    service = ODIService(InMemoryRepository())
    service.save_v2mom(
        V2MOM(vision="Make onboarding painless", methods=[_METHOD], measures=[_MEASURE])
    )
    service.repo.add_job(Job(id="job-1", name="Onboard a new engineer"))
    return service


def test_add_outcome_stores_two_objectives() -> None:
    service = _service()

    outcome = service.add_outcome(
        job_id="job-1",
        statement=_STATEMENT,
        importance=8,
        satisfaction=4,
        objectives=[
            {"field": "method", "text": _METHOD},
            {"field": "measure", "text": _MEASURE},
        ],
    )

    assert {(link.field, link.text) for link in outcome.trace} == {
        ("method", _METHOD),
        ("measure", _MEASURE),
    }
    assert outcome.trace[0].key == objective_key("method", _METHOD)


def test_add_outcome_refuses_an_unknown_objective_and_names_what_exists() -> None:
    service = _service()

    with pytest.raises(ValidationError) as excinfo:
        service.add_outcome(
            job_id="job-1",
            statement=_STATEMENT,
            importance=8,
            satisfaction=4,
            objectives=[{"field": "method", "text": "Ship the abandoned wizard"}],
        )

    assert _METHOD in str(excinfo.value)


def test_an_outcome_with_no_objectives_is_unlinked_not_refused() -> None:
    service = _service()

    outcome = service.add_outcome(
        job_id="job-1",
        statement=_STATEMENT,
        importance=8,
        satisfaction=4,
    )

    assert outcome.trace == []
    assert service.traceability_report().orphans == [outcome.id]


def test_add_outcome_deduplicates_a_repeated_link() -> None:
    service = _service()

    outcome = service.add_outcome(
        job_id="job-1",
        statement=_STATEMENT,
        importance=8,
        satisfaction=4,
        objectives=[
            {"field": "method", "text": _METHOD},
            {"field": "method", "text": _METHOD},
        ],
    )

    assert len(outcome.trace) == 1


def test_update_outcome_replaces_the_links() -> None:
    service = _service()
    outcome = service.add_outcome(
        job_id="job-1",
        statement=_STATEMENT,
        importance=8,
        satisfaction=4,
        objectives=[{"field": "method", "text": _METHOD}],
    )

    updated = service.update_outcome(
        outcome.id,
        {"objectives": [{"field": "measure", "text": _MEASURE}]},
    )

    assert [(link.field, link.text) for link in updated.trace] == [("measure", _MEASURE)]


def test_update_outcome_can_clear_the_links() -> None:
    service = _service()
    outcome = service.add_outcome(
        job_id="job-1",
        statement=_STATEMENT,
        importance=8,
        satisfaction=4,
        objectives=[{"field": "method", "text": _METHOD}],
    )

    updated = service.update_outcome(outcome.id, {"objectives": []})

    assert updated.trace == []


def test_update_outcome_without_objectives_leaves_the_links_untouched() -> None:
    service = _service()
    outcome = service.add_outcome(
        job_id="job-1",
        statement=_STATEMENT,
        importance=8,
        satisfaction=4,
        objectives=[{"field": "method", "text": _METHOD}],
    )

    updated = service.update_outcome(outcome.id, {"importance": 9.0})

    assert [(link.field, link.text) for link in updated.trace] == [("method", _METHOD)]


def test_update_outcome_refuses_an_unknown_objective() -> None:
    service = _service()
    outcome = service.add_outcome(
        job_id="job-1",
        statement=_STATEMENT,
        importance=8,
        satisfaction=4,
    )

    with pytest.raises(ValidationError):
        service.update_outcome(
            outcome.id,
            {"objectives": [{"field": "measure", "text": "Ship the abandoned wizard"}]},
        )
