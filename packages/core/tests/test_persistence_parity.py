"""No link of the persistence checklist may be left out.

A new ODI entity has to appear in the schema registry, in both repositories, in
the event replay, in the ``Repository`` protocol, in the service's write path and
in the tool contract. A new field has to survive the round trip through each
store. This test enumerates the links instead of naming them one at a time in a
handler, so an increment that adds a model or a field cannot quietly skip a layer.
"""

from __future__ import annotations

import inspect
import re
from typing import Any, get_args, get_origin, get_type_hints

import pytest
from agentic_odi_core.contract import TOOL_SPECS
from agentic_odi_core.models import (
    V2MOM,
    BusinessValue,
    CustomerOutcome,
    Direction,
    Evidence,
    Job,
    JobStage,
    Origin,
    Outcome,
    ScheduledWork,
    Segment,
    Signal,
    SignalKind,
    Step,
    Strategy,
    StrategyKind,
    ValueMetric,
)
from agentic_odi_core.repository import InMemoryRepository, Repository
from agentic_odi_core.schema import _SCHEMA_MODELS, odi_schema
from agentic_odi_core.services import ODIService
from agentic_odi_core.sqlite_repository import SQLiteRepository

#: The entities whose rows say where they came from.
ORIGIN_MODELS: tuple[type[Any], ...] = (Job, Step, Outcome, Evidence)

#: Every labeled row is about this job, in this ODI statement shape.
STATEMENT = "Minimize the time it takes to sync a secret when deploying"

#: The write tool that carries each labeled model onto the MCP surface.
ORIGIN_TOOLS = {
    "Job": "add_job",
    "Step": "add_step",
    "Outcome": "add_outcome",
    "Evidence": "add_evidence",
}

#: ``model name -> the repository getter that reads one row back``.
ORIGIN_GETTERS = {"Job": "job", "Step": "step", "Outcome": "outcome", "Evidence": "evidence"}

#: ``entity dict name -> (repository write method, the row to write)``.
ENTITY_ROWS: dict[str, tuple[str, Any]] = {
    "jobs": (
        "add_job",
        Job(id="job-1", name="Sync Secrets"),
    ),
    "steps": (
        "add_step",
        Step(id="step-1", job_id="job-1", name="Locate credentials", order=2, stage="locate"),
    ),
    "outcomes": (
        "add_outcome",
        Outcome(
            id="out-1",
            job_id="job-1",
            statement=STATEMENT,
            importance=9.0,
            satisfaction=3.0,
        ),
    ),
    "customer_outcomes": (
        "add_customer_outcome",
        CustomerOutcome(
            id="co-1",
            job_id="job-1",
            customer_value={
                "direction": Direction.MINIMIZE,
                "unit_of_measure": "time",
                "object_of_control": "the time it takes to sync",
                "statement": STATEMENT,
                "importance": 9.0,
                "satisfaction": 3.0,
                "value_metrics": [
                    ValueMetric(
                        name="drift",
                        direction=Direction.MINIMIZE,
                        unit_of_measure="errors",
                        importance=8.0,
                        satisfaction=2.0,
                    )
                ],
            },
            business_value=BusinessValue(
                category="operational_efficiency", statement="Cut incident time"
            ),
        ),
    ),
    "evidence": (
        "add_evidence",
        Evidence(
            id="evd-1",
            source_name="gong",
            source_kind="manual",
            name="Customer call",
            content="We lost two hours to a missing secret.",
        ),
    ),
    "signals": (
        "add_signal",
        Signal(id="sig-1", kind=SignalKind.JOB_ADDED, title="Job added", fingerprint="f" * 64),
    ),
    "scheduled_work": (
        "add_scheduled_work",
        ScheduledWork(id="sw-1", name="Nightly re-score", schedule_expression="+1h"),
    ),
    "segments": (
        "add_segment",
        Segment(
            id="seg-1",
            job_id="job-1",
            name="Platform engineers",
            people="engineers who rotate secrets",
            job_statement="Keep secrets in sync",
            outcome_ids=["out-1"],
            rationale="one underserved outcome",
            confidence=0.6,
        ),
    ),
    "strategies": (
        "add_strategy",
        Strategy(
            id="str-1",
            kind=StrategyKind.DIFFERENTIATED,
            segment_id="seg-1",
            thesis="Serve the underserved outcomes first",
            rejected=[{"kind": "disruptive", "why": "no evidence"}],
        ),
    ),
}

CREATED_BRANCH = re.compile(
    r'et == "([A-Z][A-Z_]+)_CREATED":\s*\n\s*self\.(\w+)\[p\["id"\]\] = (\w+)\.model_validate'
)


def _store_entities() -> dict[str, tuple[str, type[Any]]]:
    """Map each entity dict name to ``(schema model name, model class)``."""
    return {
        name: (get_args(hint)[1].__name__, get_args(hint)[1])
        for name, hint in get_type_hints(Repository).items()
        if get_origin(hint) is dict
    }


def _created_branches() -> list[tuple[str, str, str]]:
    """``(EVENT, entity dict, model)`` for every branch ``_apply_event`` replays."""
    return CREATED_BRANCH.findall(inspect.getsource(SQLiteRepository._apply_event))


# -- entity parity ------------------------------------------------------------


def test_every_stored_entity_has_a_published_schema() -> None:
    missing = sorted(
        model_name
        for model_name, _ in _store_entities().values()
        if model_name not in _SCHEMA_MODELS
    )
    assert not missing, f"{missing} is stored by the repository but missing from _SCHEMA_MODELS"


def test_both_repositories_carry_the_same_entity_dicts(tmp_path) -> None:
    expected = set(_store_entities())
    in_memory = {name for name in vars(InMemoryRepository()) if name in expected}
    sqlite_repo = SQLiteRepository(db_path=str(tmp_path / "parity.db"))
    try:
        assert in_memory == expected, "InMemoryRepository is missing an entity dict"
        assert expected <= set(vars(sqlite_repo)), "SQLiteRepository is missing an entity dict"
    finally:
        sqlite_repo.close()


def test_event_replay_covers_every_entity_exactly_once() -> None:
    branches = _created_branches()
    events = [event for event, _, _ in branches]
    assert len(events) == len(set(events)), "two branches replay the same CREATED event"

    replayed = {attr for _, attr, _ in branches}
    expected = set(_store_entities())
    missing = sorted(expected - replayed)
    extra = sorted(replayed - expected)
    assert not missing and not extra, (
        f"{missing} is stored but never replayed; {extra} is replayed but not declared"
    )


def test_event_replay_validates_the_model_the_protocol_declares() -> None:
    entities = _store_entities()
    for _, attr, model_name in _created_branches():
        assert entities[attr][0] == model_name, attr


@pytest.mark.parametrize("name", sorted(_store_entities()))
def test_a_written_entity_survives_a_store_reload(tmp_path, name: str) -> None:
    """The row must come back from the event log, not from process memory."""
    path = str(tmp_path / f"{name}.db")
    add, row = ENTITY_ROWS[name]
    writer = SQLiteRepository(db_path=path)
    try:
        getattr(writer, add)(row)
    finally:
        writer.close()

    reader = SQLiteRepository(db_path=path)
    try:
        assert getattr(reader, name), f"{name} did not replay from the event log"
    finally:
        reader.close()


# -- the origin field ---------------------------------------------------------


@pytest.mark.parametrize("model", ORIGIN_MODELS, ids=lambda m: m.__name__)
def test_origin_is_a_bounded_field_on_every_labeled_entity(model) -> None:
    field = model.model_fields.get("origin")
    assert field is not None, f"{model.__name__} has no origin field"
    assert field.default == "user"
    assert set(get_args(field.annotation)) == {"user", "demo", "sample", "imported"}


@pytest.mark.parametrize("name", sorted(ORIGIN_TOOLS))
def test_origin_appears_in_the_published_schema(name: str) -> None:
    assert "origin" in odi_schema()[name]["properties"]


@pytest.mark.parametrize("tool", sorted(ORIGIN_TOOLS.values()))
def test_origin_is_an_optional_argument_on_the_write_contract(tool: str) -> None:
    assert "origin" in TOOL_SPECS[tool].arguments, f"{tool} does not expose origin"
    assert "origin" not in TOOL_SPECS[tool].required


@pytest.mark.parametrize("model_name", sorted(ORIGIN_TOOLS))
def test_the_service_write_path_accepts_origin(model_name: str) -> None:
    method = getattr(ODIService, ORIGIN_TOOLS[model_name])
    parameter = inspect.signature(method).parameters["origin"]
    assert parameter.default == "user"
    assert set(get_args(get_type_hints(method)["origin"])) == {"user", "demo", "sample", "imported"}


def _write_labeled_row(service: ODIService, model_name: str, origin: Origin) -> Any:
    if model_name == "Job":
        return service.add_job("Sync Secrets", id="job-1", origin=origin)
    service.add_job("Sync Secrets", id="job-1")
    if model_name == "Step":
        return service.add_step(
            "job-1",
            "Locate credentials",
            2,
            stage=JobStage.LOCATE,
            allow_empty_job_map=True,
            id="step-1",
            origin=origin,
        )
    if model_name == "Outcome":
        return service.add_outcome(
            "job-1", STATEMENT, importance=9.0, satisfaction=3.0, id="out-1", origin=origin
        )
    return service.add_evidence(
        source_name="gong",
        source_kind="manual",
        name="Customer call",
        content="We lost two hours to a missing secret.",
        id="evd-1",
        origin=origin,
    )


@pytest.mark.parametrize("model_name", sorted(ORIGIN_TOOLS))
@pytest.mark.parametrize("persistent", [True, False], ids=["sqlite", "in-memory"])
def test_origin_reaches_the_store_and_comes_back(
    model_name: str, persistent: bool, tmp_path
) -> None:
    """A field that only survives the object it was set on is not persisted."""
    path = str(tmp_path / f"{model_name}.db")
    repo = SQLiteRepository(db_path=path) if persistent else InMemoryRepository()
    service = ODIService(repo)
    saved = _write_labeled_row(service, model_name, "demo")
    assert saved.origin == "demo"

    if persistent:
        service.repo.close()
        service = ODIService(SQLiteRepository(db_path=path))
    getter = getattr(service.repo, f"get_{ORIGIN_GETTERS[model_name]}")
    reloaded = getter(saved.id)
    assert reloaded is not None
    assert reloaded.origin == "demo"


# -- nothing outside the labeled entities pretends to carry origin ------------


@pytest.mark.parametrize(
    "model",
    [CustomerOutcome, Signal, ScheduledWork, Segment, Strategy, V2MOM],
    ids=lambda m: m.__name__,
)
def test_entities_outside_the_loader_stay_unlabeled(model) -> None:
    assert "origin" not in model.model_fields
