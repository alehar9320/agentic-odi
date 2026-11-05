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
