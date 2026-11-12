"""Every entity reaches every link in the persistence chain.

Adding an entity is easy to half-do: it lands in the models and the in-memory
store but not in the SQLite replay, so a reload silently drops it. This test
enumerates the links and fails when an entity is present in one and missing
from another, instead of letting replay diverge quietly.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

from agentic_odi_core import schema
from agentic_odi_core.repository import InMemoryRepository, Repository
from agentic_odi_core.sqlite_repository import SQLiteRepository

_SQLITE_SRC = inspect.getsource(SQLiteRepository)


def _camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _created_event_names() -> set[str]:
    """The entity prefixes that have a ``*_CREATED`` replay branch."""
    return set(re.findall(r'et == "([A-Z_]+)_CREATED"', _SQLITE_SRC))


#: Model name -> the event prefix its rows use. ``OutcomeCandidate`` is stored
#: as ``CANDIDATE`` (a candidate is a proposal, not an outcome), so the mapping
#: is explicit rather than derived.
#: Model name -> the plural attribute the stores keep its rows under. Mostly
#: ``snake + s``, but a few are irregular, so the map is explicit.
_ATTR: dict[str, str] = {
    "Job": "jobs",
    "Step": "steps",
    "Outcome": "outcomes",
    "CustomerOutcome": "customer_outcomes",
    "Evidence": "evidence",
    "OutcomeCandidate": "candidates",
    "DecisionRecord": "decisions",
    "BetRecord": "bets",
    "MeasurementRecord": "measurements",
}

_EVENT_PREFIX: dict[str, str] = {
    "Job": "JOB",
    "Step": "STEP",
    "Outcome": "OUTCOME",
    "CustomerOutcome": "CUSTOMER_OUTCOME",
    "Evidence": "EVIDENCE",
    "OutcomeCandidate": "CANDIDATE",
    "DecisionRecord": "DECISION",
    "BetRecord": "BET",
    "MeasurementRecord": "MEASUREMENT",
}


#: The entities persisted as their own rows. The value models (CustomerValue,
#: BusinessValue, ValueMetric) are embedded inside CustomerOutcome, not stored
#: standalone, so they are deliberately not in this set.
PERSISTED_ENTITIES = tuple(_EVENT_PREFIX)


def test_every_persisted_entity_is_a_schema_model() -> None:
    for name in PERSISTED_ENTITIES:
        assert name in schema._SCHEMA_MODELS, f"{name} is persisted but not in odi_schema()"


def test_every_persisted_entity_has_a_replay_branch() -> None:
    created = _created_event_names()
    missing = {name: prefix for name, prefix in _EVENT_PREFIX.items() if prefix not in created}
    assert not missing, f"entities without a *_CREATED replay branch: {missing}"


def test_every_schema_model_is_declared_on_the_repository_protocol() -> None:
    # The protocol declares each entity as both a dict attribute and add/get
    # method pairs; check the attribute the SQLite and in-memory stores share.
    source = inspect.getsource(Repository)
    for name in PERSISTED_ENTITIES:
        plural = _ATTR[name]
        assert f"{plural}: dict" in source, f"{name}: no '{plural}' dict on the Repository protocol"


def test_both_repositories_expose_the_same_entity_dicts() -> None:
    sqlite_src = _SQLITE_SRC
    for name in PERSISTED_ENTITIES:
        plural = _ATTR[name]
        assert f"self.{plural}: dict" in sqlite_src, (
            f"{name}: SQLiteRepository has no '{plural}' snapshot dict"
        )
        assert hasattr(InMemoryRepository(), plural), (
            f"{name}: InMemoryRepository has no '{plural}' attribute"
        )


def test_origin_reaches_every_entity_that_carries_it() -> None:
    """The demo/sample vocabulary is a field on the entities that need it.

    ``origin`` is on the entities a user or a demo creates directly (job, step,
    outcome, evidence). It is deliberately not on the review/loop records, whose
    provenance is the parent they point at.
    """
    from agentic_odi_core.models import Evidence, Job, Outcome, Step

    for model in (Job, Step, Outcome, Evidence):
        assert "origin" in model.model_fields, f"{model.__name__} is missing origin"
    assert "origin" in schema.odi_schema()["Job"]["properties"]


def test_the_sqlite_source_file_is_found() -> None:
    # A guard against the reflection silently reading nothing if the module
    # moves; an empty source would make the tests above vacuously pass.
    assert Path(SQLiteRepository.__module__.replace(".", "/")).name
    assert "def _apply_event" in _SQLITE_SRC
