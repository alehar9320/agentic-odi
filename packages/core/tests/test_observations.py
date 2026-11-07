"""What the agent believes is a proposal until the person says otherwise."""

from __future__ import annotations

import pytest
from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.services import ObservationNotFoundError
from agentic_odi_core.sqlite_repository import SQLiteRepository


def _sqlite(tmp_path) -> SQLiteRepository:
    return SQLiteRepository(str(tmp_path / "odi.db"), device_id="device-a")


@pytest.fixture(params=["memory", "sqlite"])
def service(request, tmp_path) -> ODIService:
    repo = InMemoryRepository() if request.param == "memory" else _sqlite(tmp_path)
    return ODIService(repo)


def test_remember_proposes_rather_than_confirms(service: ODIService) -> None:
    observation = service.remember("Accountable for activation.", category="career")

    assert observation.status == "proposed"
    assert observation.category == "career"
    # Confidence is what the agent claims, not what the person agreed to.
    assert observation.confidence == 0.5


def test_the_person_said_it_is_a_fact(service: ODIService) -> None:
    observation = service.remember("Prefers short updates.", category="preference")

    confirmed = service.set_observation_status(observation.id, "confirmed")

    assert confirmed.status == "confirmed"
    assert [item.id for item in service.confirmed_observations()] == [observation.id]


def test_an_empty_note_is_rejected(service: ODIService) -> None:
    with pytest.raises(ValidationError):
        service.remember("   ")


def test_a_guess_is_never_carried_into_a_prompt(service: ODIService) -> None:
    proposed = service.remember("Maybe they own activation.")
    confirmed = service.remember("They own activation.", category="career")
    service.set_observation_status(confirmed.id, "confirmed")

    assert [item.id for item in service.confirmed_observations()] == [confirmed.id]
    assert proposed.id not in [item.id for item in service.confirmed_observations()]


def test_a_dismissed_observation_never_comes_back(service: ODIService) -> None:
    wrong = service.remember("They report to the CRO.")
    service.set_observation_status(wrong.id, "dismissed")

    assert service.get_observation(wrong.id).status == "dismissed"
    assert service.confirmed_observations() == []
    # The log keeps it so the person can see what was thrown away; no read model
    # that feeds a prompt asks for dismissed rows.
    assert [item.id for item in service.list_observations(status="dismissed")] == [wrong.id]
    assert [item.id for item in service.list_observations(status="confirmed")] == []

    service.remember("They report to the VP of Product.")
    service.set_observation_status(service.list_observations()[0].id, "confirmed")

    assert wrong.id not in [item.id for item in service.confirmed_observations()]
    assert wrong.text not in [item.text for item in service.confirmed_observations()]


def test_an_unknown_status_is_rejected(service: ODIService) -> None:
    observation = service.remember("Owns activation.")

    with pytest.raises(ValidationError):
        service.set_observation_status(observation.id, "guessed")  # type: ignore[arg-type]


def test_editing_an_observation_keeps_the_person_in_charge(service: ODIService) -> None:
    observation = service.remember("Owns activation.")

    edited = service.update_observation(
        observation.id, {"text": "Owns activation and retention.", "confidence": 0.9}
    )

    assert edited.text == "Owns activation and retention."
    assert edited.confidence == 0.9
    assert edited.status == "proposed"


def test_an_observation_keeps_its_provenance(service: ODIService) -> None:
    conversation = service.start_conversation()
    turn = service.append_message(conversation.id, "user", "I own activation end to end.")

    observation = service.remember(
        "Owns activation.",
        conversation_id=conversation.id,
        source_message_id=turn.id,
        data={"quote": "end to end"},
    )

    assert observation.conversation_id == conversation.id
    assert observation.source_message_id == turn.id
    assert observation.data == {"quote": "end to end"}


def test_forgetting_one_is_final(service: ODIService) -> None:
    observation = service.remember("Owns activation.")

    service.delete_observation(observation.id)

    with pytest.raises(ObservationNotFoundError):
        service.get_observation(observation.id)
    with pytest.raises(ObservationNotFoundError):
        service.delete_observation(observation.id)
    with pytest.raises(ObservationNotFoundError):
        service.update_observation(observation.id, {"status": "confirmed"})


def test_listing_pages_newest_first(service: ODIService) -> None:
    first = service.remember("One")
    service.remember("Two")
    third = service.remember("Three")

    newest_first = [item.id for item in service.list_observations()]
    assert len(newest_first) == 3
    assert {newest_first[0], newest_first[-1]} == {third.id, first.id}
    assert [item.id for item in service.list_observations(limit=1, offset=1)] == [
        newest_first[1],
    ]


def test_a_reopen_reads_back_what_was_written(tmp_path) -> None:
    writer = ODIService(_sqlite(tmp_path))
    observation = writer.remember("Accountable for activation.", category="career")
    writer.set_observation_status(observation.id, "confirmed")

    reader = ODIService(_sqlite(tmp_path))
    reopened = reader.get_observation(observation.id)

    assert reopened is not None
    assert reopened.text == observation.text
    assert reopened.status == "confirmed"
    assert [item.id for item in reader.confirmed_observations()] == [observation.id]


def test_a_dismissed_observation_stays_dismissed_across_a_reopen(tmp_path) -> None:
    writer = ODIService(_sqlite(tmp_path))
    observation = writer.remember("They report to the CRO.")
    writer.set_observation_status(observation.id, "dismissed")

    reader = ODIService(_sqlite(tmp_path))

    assert reader.get_observation(observation.id).status == "dismissed"
    assert reader.confirmed_observations() == []
