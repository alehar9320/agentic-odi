"""A NextStep is the promise the user made as a session ended.

ALH-146 (M0-14). The product records what the user knows but never what they
intend to do, so a return visit has nothing to pick up. This entity is that
intention, stored rather than kept in the browser, because a greeting about a
step that vanished on a cache clear would be a lie. The model owns the invariants
it can check alone: a step needs a real line of text, a resolution never arrives
without the moment it happened, and ``is_open`` is the single definition of
"still outstanding" that every surface reads.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from agentic_odi_core.models import NextStep
from agentic_odi_core.schema import odi_schema
from pydantic import ValidationError as PydanticValidationError


def test_a_bare_step_gets_an_identity_and_starts_open() -> None:
    step = NextStep(text="Talk to two support leads")

    assert step.id
    assert step.created_at.tzinfo is not None
    assert step.is_open is True
    assert step.due_at is None
    assert step.resolved_at is None
    assert step.resolution is None
    assert step.superseded_at is None
    assert step.outcome_id is None


def test_text_is_required_and_cannot_be_blank_or_whitespace() -> None:
    with pytest.raises(PydanticValidationError):
        NextStep(text="")
    with pytest.raises(PydanticValidationError):
        NextStep(text="   ")


def test_text_is_stored_trimmed_so_a_greeting_cannot_render_padding() -> None:
    assert NextStep(text="  Rewrite the screener\n").text == "Rewrite the screener"


def test_a_step_round_trips_through_json() -> None:
    step = NextStep(text="Ask the payer what they do today", outcome_id="o-1")

    assert NextStep.model_validate(step.model_dump(mode="json")) == step


def test_a_resolution_never_arrives_without_a_resolved_at() -> None:
    with pytest.raises(PydanticValidationError):
        NextStep(text="Rewrite the screener", resolution="spoke to both leads")
    with pytest.raises(PydanticValidationError):
        NextStep(text="Rewrite the screener", resolved_at=datetime.now(timezone.utc))


def test_open_means_neither_resolved_nor_superseded() -> None:
    now = datetime.now(timezone.utc)

    assert NextStep(text="x", resolved_at=now, resolution="done").is_open is False
    assert NextStep(text="x", superseded_at=now).is_open is False


def test_the_entity_is_part_of_the_published_schema() -> None:
    schema = odi_schema()

    assert "NextStep" in schema
    assert "text" in schema["NextStep"]["properties"]
    assert "is_open" not in schema["NextStep"]["properties"]


def _both_repositories(tmp_path):
    """The same expectations against the event-sourced store and the plain one.

    ``SQLiteRepository`` replays ``NEXT_STEP_*`` events; ``InMemoryRepository``
    holds dicts. A greeting that reads a step the store cannot return identically
    in both is a greeting that will lie on one backend.
    """
    from agentic_odi_core.repository import InMemoryRepository
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    return [InMemoryRepository(), SQLiteRepository(str(tmp_path / "odi.db"))]


def test_a_step_survives_a_reopen(tmp_path) -> None:
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    step = NextStep(text="Talk to two support leads")

    assert repo.add_next_step(step).id == step.id
    reopened = SQLiteRepository(db)
    assert reopened.get_next_step(step.id) == step
    assert [s.id for s in reopened.list_next_steps()] == [step.id]


def test_a_resolution_survives_a_reopen(tmp_path) -> None:
    from datetime import datetime, timezone

    from agentic_odi_core.sqlite_repository import SQLiteRepository

    db = str(tmp_path / "odi.db")
    repo = SQLiteRepository(db)
    repo.add_next_step(NextStep(text="Rewrite the screener"))
    resolved_at = datetime.now(timezone.utc).replace(microsecond=0)

    updated = repo.update_next_step(
        repo.list_next_steps()[0].id,
        {"resolved_at": resolved_at.isoformat(), "resolution": "Cut two questions"},
    )
    assert updated is not None and updated.is_open is False

    reopened = SQLiteRepository(db)
    stored = reopened.list_next_steps()[0]
    assert stored.resolved_at == resolved_at
    assert stored.resolution == "Cut two questions"


def test_supersede_is_expressed_in_the_events_not_only_in_the_service(tmp_path) -> None:
    """Replaying a stream that already carries a superseded step yields one open step.

    The supersede has to be part of what is written down. If it lived only in the
    service call, a second machine opening the same file would show two
    outstanding promises, and the greeting would pick one at random.
    """
    from datetime import datetime, timezone

    from agentic_odi_core.intent_store import IntentStore
    from agentic_odi_core.sqlite_repository import SQLiteRepository

    db = str(tmp_path / "odi.db")
    first = NextStep(text="Talk to two support leads")
    second = NextStep(text="Ask the payer what they do today")
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    store = IntentStore(db)
    store.append("NEXT_STEP_CREATED", first.model_dump(mode="json"))
    store.append("NEXT_STEP_UPDATED", {"id": first.id, "updates": {"superseded_at": stamp}})
    store.append("NEXT_STEP_CREATED", second.model_dump(mode="json"))
    store.close()

    repo = SQLiteRepository(db)
    open_steps = [s for s in repo.list_next_steps() if s.is_open]
    assert [s.id for s in open_steps] == [second.id]
    superseded = repo.get_next_step(first.id)
    assert superseded is not None and superseded.superseded_at is not None


def test_the_in_memory_repository_matches(tmp_path) -> None:
    for repo in _both_repositories(tmp_path):
        step = NextStep(text="Draft the interview guide")
        repo.add_next_step(step)
        assert repo.get_next_step(step.id) == step
        assert repo.get_next_step("nope") is None
        assert step in repo.list_next_steps()
        updated = repo.update_next_step(step.id, {"text": "Draft the screener"})
        assert updated is not None and updated.text == "Draft the screener"
        assert repo.update_next_step("nope", {"text": "x"}) is None
