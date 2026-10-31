"""Tests for the Living Studio's local memory store."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from agentic_odi_studio_api.studio.memory import (
    OBSERVATION_KINDS,
    ConversationNotFoundError,
    MemoryError,
    ObservationNotFoundError,
    StudioMemory,
    default_db_path,
)


@pytest.fixture()
def memory() -> Iterator[StudioMemory]:
    store = StudioMemory(":memory:")
    yield store
    store.close()


def test_create_conversation_starts_untitled(memory: StudioMemory) -> None:
    conversation = memory.create_conversation()
    assert conversation.id
    assert conversation.title == ""
    assert memory.latest_conversation() == conversation


def test_first_user_turn_names_the_conversation(memory: StudioMemory) -> None:
    conversation = memory.create_conversation()
    memory.append_turn(conversation.id, "user", "  I own activation for self-serve trials  ")
    memory.append_turn(conversation.id, "assistant", "Tell me where it breaks.")

    latest = memory.latest_conversation()
    assert latest is not None
    assert latest.id == conversation.id
    assert latest.title == "I own activation for self-serve trials"


def test_assistant_turn_does_not_replace_the_title(memory: StudioMemory) -> None:
    conversation = memory.create_conversation()
    memory.append_turn(conversation.id, "user", "First message")
    memory.append_turn(conversation.id, "assistant", "Reply")
    latest = memory.latest_conversation()
    assert latest is not None
    assert latest.title == "First message"


def test_turns_round_trip_in_order(memory: StudioMemory) -> None:
    conversation = memory.create_conversation()
    memory.append_turn(conversation.id, "user", "one")
    memory.append_turn(conversation.id, "assistant", "two")

    turns = memory.list_turns(conversation.id)
    assert [turn.role for turn in turns] == ["user", "assistant"]
    assert [turn.content for turn in turns] == ["one", "two"]


def test_unknown_conversation_is_rejected(memory: StudioMemory) -> None:
    with pytest.raises(ConversationNotFoundError):
        memory.append_turn("missing", "user", "hello")
    with pytest.raises(ConversationNotFoundError):
        memory.list_turns("missing")


def test_add_observation_defaults_to_suggested(memory: StudioMemory) -> None:
    observation = memory.add_observation("career", "Wants to be known for activation.")
    assert observation.status == "suggested"
    assert observation.confidence == 0.5
    assert observation.data == {}
    assert memory.list_observations() == [observation]


def test_observation_kinds_are_validated(memory: StudioMemory) -> None:
    with pytest.raises(ValueError):
        memory.add_observation("nonsense", "text")
    assert "career" in OBSERVATION_KINDS


def test_observation_text_must_be_present(memory: StudioMemory) -> None:
    with pytest.raises(ValueError):
        memory.add_observation("career", "   ")


def test_observations_round_trip_data(memory: StudioMemory) -> None:
    observation = memory.add_observation(
        "opportunity", "Activation is stuck.", data={"job_id": "job-1"}, confidence=0.8
    )
    stored = memory.list_observations()[0]
    assert stored.id == observation.id
    assert stored.data == {"job_id": "job-1"}
    assert stored.confidence == 0.8


def test_dismissed_observations_are_hidden_by_default(memory: StudioMemory) -> None:
    keep = memory.add_observation("business", "Growth is the mandate.")
    drop = memory.add_observation("business", "A wrong guess.")
    memory.update_observation(drop.id, status="dismissed")

    assert [item.id for item in memory.list_observations()] == [keep.id]
    assert len(memory.list_observations(include_dismissed=True)) == 2


def test_update_observation_fields(memory: StudioMemory) -> None:
    observation = memory.add_observation("constraint", "Approval is slow.")
    updated = memory.update_observation(
        observation.id, text="Legal review is slow.", status="confirmed", confidence=0.9
    )
    assert updated.text == "Legal review is slow."
    assert updated.status == "confirmed"
    assert updated.confidence == 0.9


def test_update_unknown_observation_is_rejected(memory: StudioMemory) -> None:
    with pytest.raises(ObservationNotFoundError):
        memory.update_observation("missing", status="confirmed")


def test_delete_observation(memory: StudioMemory) -> None:
    observation = memory.add_observation("preference", "Prefers short updates.")
    memory.delete_observation(observation.id)
    assert memory.list_observations() == []
    with pytest.raises(ObservationNotFoundError):
        memory.delete_observation(observation.id)


def test_memory_context_marks_status(memory: StudioMemory) -> None:
    memory.add_observation("career", "Owns activation.", status="confirmed")
    memory.add_observation("constraint", "Legal review is slow.")
    memory.add_observation("business", "Ignore this.", status="dismissed")

    context = memory.memory_context()
    assert "Owns activation." in context
    assert "Legal review is slow." in context
    assert "Ignore this." not in context
    assert "confirmed" in context


def test_memory_context_caps_suggestions(memory: StudioMemory) -> None:
    memory.add_observation("career", "confirmed fact", status="confirmed")
    for index in range(15):
        memory.add_observation("evidence", f"suggestion {index}")

    context = memory.memory_context()
    assert "confirmed fact" in context
    assert "suggestion 14" not in context


def test_clear_memory_removes_conversations_and_observations(memory: StudioMemory) -> None:
    conversation = memory.create_conversation()
    memory.append_turn(conversation.id, "user", "hello")
    memory.add_observation("career", "Owns activation.")
    memory.mark_signal("signal-1")

    memory.clear_memory()

    assert memory.latest_conversation() is None
    assert memory.list_observations() == []
    assert memory.signal_state() == {}
    with pytest.raises(ConversationNotFoundError):
        memory.list_turns(conversation.id)


def test_mark_signal_records_read_state_idempotently(memory: StudioMemory) -> None:
    first = memory.mark_signal("signal-1")
    assert first["read_at"] is not None
    assert first["dismissed_at"] is None

    # Marking again keeps the original timestamp rather than moving it.
    again = memory.mark_signal("signal-1")
    assert again["read_at"] == first["read_at"]


def test_mark_signal_can_dismiss_and_keep_a_read_mark(memory: StudioMemory) -> None:
    memory.mark_signal("signal-1")
    dismissed = memory.mark_signal("signal-1", dismissed=True)
    assert dismissed["read_at"] is not None
    assert dismissed["dismissed_at"] is not None
    assert memory.signal_state()["signal-1"]["dismissed_at"] == dismissed["dismissed_at"]


def test_mark_signal_rejects_a_blank_id(memory: StudioMemory) -> None:
    with pytest.raises(MemoryError):
        memory.mark_signal("   ")


def test_read_and_dismiss_state_survives_a_reload(tmp_path) -> None:
    db = tmp_path / "studio.db"
    first = StudioMemory(db)
    first.mark_signal("signal-1")
    first.mark_signal("signal-2", dismissed=True)
    first.close()

    # A brand-new store over the same file still knows what was read/dismissed.
    second = StudioMemory(db)
    try:
        state = second.signal_state()
        assert state["signal-1"]["read_at"] is not None
        assert state["signal-1"]["dismissed_at"] is None
        assert state["signal-2"]["dismissed_at"] is not None
    finally:
        second.close()


def test_default_db_path_prefers_environment(tmp_path, monkeypatch) -> None:
    target = tmp_path / "studio.db"
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_DB", str(target))
    assert default_db_path() == target


def test_default_db_path_falls_back_to_home(monkeypatch) -> None:
    monkeypatch.delenv("AGENTIC_ODI_STUDIO_DB", raising=False)
    assert default_db_path().name == "studio.db"
    assert default_db_path().parent.name == ".agentic-odi"


def test_a_file_backed_store_is_configured_for_concurrent_writers(tmp_path) -> None:
    store = StudioMemory(str(tmp_path / "studio.db"))
    try:
        connection = store._connection
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        store.close()
