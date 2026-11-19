"""Traceability: orphans, unfunded objectives, and drift.

The fixture is the one the issue names: two objectives and four outcomes, of
which one advances an objective, one advances nothing, and one points at text
the vision no longer holds.
"""

from __future__ import annotations

import pytest
from agentic_odi_core import (
    ODIService,
    OutcomeNotFoundError,
)
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import V2MOM, Job, Outcome
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.sqlite_repository import SQLiteRepository
from agentic_odi_core.traceability import (
    TraceLink,
    compute_traceability_report,
    normalize_objective,
    objective_key,
    objectives_from_v2mom,
)

_METHOD = "Cut time-to-first-value"
_MEASURE = "Net revenue retention above 120%"
_REMOVED = "Ship the abandoned onboarding wizard"


def _outcome(outcome_id: str, trace: list | None = None) -> Outcome:
    return Outcome(
        id=outcome_id,
        job_id="job-1",
        statement="Minimize the time it takes to onboard a new engineer when they join",
        importance=8,
        satisfaction=4,
        opportunity_score=12,
        trace=trace or [],
    )


def _linked(outcome_id: str, text: str = _METHOD) -> Outcome:
    return _outcome(
        outcome_id,
        trace=[{"field": "method", "key": objective_key("method", text), "text": text}],
    )


def _vision() -> V2MOM:
    return V2MOM(vision="Make onboarding painless", methods=[_METHOD], measures=[_MEASURE])


def _fixture() -> tuple[V2MOM, list[Outcome]]:
    """Two objectives, four outcomes: linked, orphan, drifting, linked."""
    return _vision(), [
        _linked("linked"),
        _outcome("orphan"),
        _linked("drifting", text=_REMOVED),
        _linked("linked-again"),
    ]


def test_the_fixture_yields_one_of_each() -> None:
    v2mom, outcomes = _fixture()

    report = compute_traceability_report(v2mom, outcomes)

    assert report.counts == {"orphans": 1, "unfunded": 1, "drift": 1}
    assert report.orphans == ["orphan"]
    assert [item["text"] for item in report.unfunded] == [_MEASURE]
    assert [item["outcome_id"] for item in report.drift] == ["drifting"]


def test_an_unlinked_outcome_is_never_counted_as_drift() -> None:
    v2mom, outcomes = _fixture()

    report = compute_traceability_report(v2mom, outcomes)

    assert report.drift == [
        {
            "outcome_id": "drifting",
            "field": "method",
            "key": objective_key("method", _REMOVED),
            "text": _REMOVED,
        }
    ]
    assert "orphan" not in [item["outcome_id"] for item in report.drift]


def test_an_empty_vision_says_there_is_nothing_to_check() -> None:
    report = compute_traceability_report(V2MOM(vision="A vision with no lists"), [_outcome("a")])

    assert report.objectives_defined is False
    assert report.orphans == [] and report.unfunded == [] and report.drift == []
    assert "no objectives defined" in (report.message or "").lower()
    assert report.summary() == report.message


def test_no_vision_at_all_says_the_same_thing() -> None:
    report = compute_traceability_report(None, [_outcome("a")])

    assert report.objectives_defined is False
    assert "no objectives defined" in (report.message or "").lower()


def test_a_clean_report_reads_as_clean() -> None:
    v2mom = V2MOM(methods=[_METHOD])
    outcomes = [_linked("a")]

    report = compute_traceability_report(v2mom, outcomes)

    assert report.counts == {"orphans": 0, "unfunded": 0, "drift": 0}
    assert report.summary() == "Every outcome advances an objective, and every objective is funded."


def test_rewording_a_method_drifts_but_renaming_it_back_heals() -> None:
    outcomes = [_linked("a")]
    reworded = V2MOM(methods=["Cut time to first value"])

    assert compute_traceability_report(reworded, outcomes).counts["drift"] == 1
    # Renaming back reproduces the same key, so the link resolves again.
    assert compute_traceability_report(_vision(), outcomes).counts["drift"] == 0


def test_normalization_is_case_and_punctuation_insensitive() -> None:
    assert normalize_objective("Cut  time-to-first-value.") == normalize_objective(
        "cut time-to-first-value"
    )
    assert objective_key("method", "Cut Time") == objective_key("method", "cut time.")


def test_the_same_text_in_two_lists_keeps_two_keys() -> None:
    assert objective_key("method", "x") != objective_key("measure", "x")


def test_explicit_links_are_used_when_supplied() -> None:
    report = compute_traceability_report(
        _vision(),
        [_outcome("a")],
        links=[TraceLink(outcome_id="a", field="method", text=_METHOD)],
    )

    assert report.counts == {"orphans": 0, "unfunded": 1, "drift": 0}


def test_objectives_are_read_from_methods_and_measures_only() -> None:
    v2mom = V2MOM(
        vision="v",
        values=["Act with integrity"],
        methods=["M"],
        obstacles=["Slow build"],
        measures=["K"],
    )

    fields = {(objective.field, objective.text) for objective in objectives_from_v2mom(v2mom)}

    assert fields == {("method", "M"), ("measure", "K")}


def _service_with_job() -> ODIService:
    service = ODIService(InMemoryRepository())
    service.save_v2mom(_vision())
    service.repo.add_job(Job(id="job-1", name="Onboard a new engineer"))
    return service


def test_link_outcome_refuses_unknown_text_and_names_what_exists() -> None:
    service = _service_with_job()
    outcome = service.add_outcome(
        job_id="job-1",
        statement="Minimize the time it takes to onboard a new engineer when they join",
        importance=8,
        satisfaction=4,
    )

    with pytest.raises(ValidationError) as excinfo:
        service.link_outcome(outcome.id, "method", "Ship a different wizard")

    assert _METHOD in str(excinfo.value)


def test_link_outcome_refuses_an_unknown_outcome() -> None:
    service = _service_with_job()

    with pytest.raises(OutcomeNotFoundError):
        service.link_outcome("nope", "method", _METHOD)


def test_linking_the_same_pair_twice_is_idempotent() -> None:
    service = _service_with_job()
    outcome = service.add_outcome(
        job_id="job-1",
        statement="Minimize the time it takes to onboard a new engineer when they join",
        importance=8,
        satisfaction=4,
    )

    service.link_outcome(outcome.id, "method", _METHOD)
    linked = service.link_outcome(outcome.id, "method", _METHOD)

    assert len(linked.trace) == 1


def test_unlink_removes_the_link_and_the_outcome_becomes_an_orphan() -> None:
    service = _service_with_job()
    outcome = service.add_outcome(
        job_id="job-1",
        statement="Minimize the time it takes to onboard a new engineer when they join",
        importance=8,
        satisfaction=4,
    )
    linked = service.link_outcome(outcome.id, "method", _METHOD)

    unlinked = service.unlink_outcome(outcome.id, "method", linked.trace[0].key)

    assert unlinked.trace == []
    assert service.traceability_report().orphans == [outcome.id]


def test_removing_a_method_drifts_its_links_rather_than_unlinking_them() -> None:
    service = _service_with_job()
    outcome = service.add_outcome(
        job_id="job-1",
        statement="Minimize the time it takes to onboard a new engineer when they join",
        importance=8,
        satisfaction=4,
    )
    service.link_outcome(outcome.id, "method", _METHOD)

    service.save_v2mom(V2MOM(methods=["A different method"]))

    report = service.traceability_report()
    assert report.counts["drift"] == 1
    assert report.drift[0]["text"] == _METHOD
    assert report.orphans == []


def test_deleting_an_outcome_removes_its_links() -> None:
    service = _service_with_job()
    outcome = service.add_outcome(
        job_id="job-1",
        statement="Minimize the time it takes to onboard a new engineer when they join",
        importance=8,
        satisfaction=4,
    )
    service.link_outcome(outcome.id, "method", _METHOD)

    service.delete_outcome(outcome.id)

    report = service.traceability_report()
    assert report.orphans == []
    assert report.unfunded != []
    assert service.list_alignments() == []


def test_the_report_never_writes() -> None:
    service = _service_with_job()
    outcome = service.add_outcome(
        job_id="job-1",
        statement="Minimize the time it takes to onboard a new engineer when they join",
        importance=8,
        satisfaction=4,
    )
    service.link_outcome(outcome.id, "method", _METHOD)
    before = service.get_outcome(outcome.id)

    service.traceability_report()
    service.traceability_report()

    assert service.get_outcome(outcome.id) == before


def _sqlite_service(tmp_path) -> tuple[ODIService, str]:
    db = str(tmp_path / "odi.db")
    return ODIService(SQLiteRepository(db_path=db)), db


def test_a_link_survives_a_reload_from_the_event_log(tmp_path) -> None:
    service, db = _sqlite_service(tmp_path)
    service.save_v2mom(_vision())
    service.repo.add_job(Job(id="job-1", name="Onboard a new engineer"))
    outcome = service.add_outcome(
        job_id="job-1",
        statement="Minimize the time it takes to onboard a new engineer when they join",
        importance=8,
        satisfaction=4,
    )

    service.link_outcome(outcome.id, "method", _METHOD)
    reopened = ODIService(SQLiteRepository(db_path=db))

    assert reopened.traceability_report().counts == {"orphans": 0, "unfunded": 1, "drift": 0}
    assert reopened.list_alignments() == [
        {
            "outcome_id": outcome.id,
            "field": "method",
            "key": objective_key("method", _METHOD),
            "text": _METHOD,
        }
    ]


def test_an_unlink_survives_a_reload_as_an_orphan(tmp_path) -> None:
    service, db = _sqlite_service(tmp_path)
    service.save_v2mom(_vision())
    service.repo.add_job(Job(id="job-1", name="Onboard a new engineer"))
    outcome = service.add_outcome(
        job_id="job-1",
        statement="Minimize the time it takes to onboard a new engineer when they join",
        importance=8,
        satisfaction=4,
    )
    service.link_outcome(outcome.id, "method", _METHOD)

    service.unlink_outcome(outcome.id, "method", objective_key("method", _METHOD))
    reopened = ODIService(SQLiteRepository(db_path=db))

    assert reopened.traceability_report().orphans == [outcome.id]
    assert reopened.list_alignments() == []


def test_the_vision_survives_a_reload(tmp_path) -> None:
    service, db = _sqlite_service(tmp_path)
    service.save_v2mom(_vision())

    reopened = ODIService(SQLiteRepository(db_path=db))

    assert reopened.get_v2mom() == _vision()
    assert [item["text"] for item in reopened.traceability_report().unfunded] == [_METHOD, _MEASURE]
