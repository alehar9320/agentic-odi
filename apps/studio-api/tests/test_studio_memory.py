"""The Studio's memory is the core event store, reached through one facade."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from agentic_odi_core import Conversation, Observation
from agentic_odi_core.sqlite_repository import SQLiteRepository
from agentic_odi_studio_api.studio.memory import (
    MAX_CONTEXT_CHARS,
    OBSERVATION_CATEGORIES,
    ConversationNotFoundError,
    ObservationNotFoundError,
    StudioMemory,
    default_db_path,
)


@pytest.fixture()
def memory() -> Iterator[StudioMemory]:
    store = StudioMemory(":memory:")
    yield store
    store.close()


def _seed(store: StudioMemory) -> str:
    conversation = store.create_conversation()
    store.append_turn(conversation.id, "user", "one", "m-1")
    store.append_turn(conversation.id, "assistant", "two", "m-2", "m-1")
    return conversation.id


# -- conversations ---------------------------------------------------------


def test_create_conversation_starts_untitled(memory: StudioMemory) -> None:
    conversation = memory.create_conversation()
    assert conversation.id
    assert conversation.title is None
    assert conversation.head_id is None
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
    conversation_id = _seed(memory)

    turns = memory.list_turns(conversation_id)
    assert [turn.role for turn in turns] == ["user", "assistant"]
    assert [turn.content for turn in turns] == ["one", "two"]
    assert [turn.id for turn in turns] == ["m-1", "m-2"]


def test_parts_round_trip_with_the_turn(memory: StudioMemory) -> None:
    conversation = memory.create_conversation()
    memory.append_turn(
        conversation.id,
        "assistant",
        "here they are",
        "m-2",
        parts=[{"kind": "ui", "id": "ui-1", "node": {"component": "opportunity-board"}}],
    )

    turn = memory.list_turns(conversation.id)[-1]
    assert turn.parts[0]["node"]["component"] == "opportunity-board"


def test_the_head_follows_the_newest_turn(memory: StudioMemory) -> None:
    conversation_id = _seed(memory)
    assert memory.get_conversation(conversation_id).head_id == "m-2"  # type: ignore[union-attr]

    memory.set_head(conversation_id, "m-1")
    assert memory.get_conversation(conversation_id).head_id == "m-1"  # type: ignore[union-attr]


def test_archiving_keeps_the_thread_readable(memory: StudioMemory) -> None:
    conversation_id = _seed(memory)
    archived = memory.set_archived(conversation_id, True)

    assert archived.archived is True
    assert memory.get_conversation(conversation_id) is not None
    assert len(memory.list_turns(conversation_id)) == 2
    assert memory.set_archived(conversation_id, False).archived is False


def test_unknown_conversation_is_rejected(memory: StudioMemory) -> None:
    with pytest.raises(ConversationNotFoundError):
        memory.append_turn("missing", "user", "hello")
    with pytest.raises(ConversationNotFoundError):
        memory.list_turns("missing")
    with pytest.raises(ConversationNotFoundError):
        memory.set_head("missing", "m-1")


def test_unknown_role_is_rejected(memory: StudioMemory) -> None:
    conversation = memory.create_conversation()
    with pytest.raises(ValueError):
        memory.append_turn(conversation.id, "god", "hello")


# -- persistence -----------------------------------------------------------


def test_the_thread_survives_a_restart(tmp_path: Path) -> None:
    path = str(tmp_path / "odi.db")
    first = StudioMemory(path)
    conversation = first.create_conversation()
    first.append_turn(conversation.id, "user", "list my jobs", "m-1")
    first.add_observation("career", "Owns activation.", status="confirmed")

    reopened = StudioMemory(path)
    turns = reopened.list_turns(conversation.id)
    assert [turn.content for turn in turns] == ["list my jobs"]
    assert reopened.get_conversation(conversation.id).head_id == "m-1"  # type: ignore[union-attr]
    assert [item.text for item in reopened.list_observations()] == ["Owns activation."]


def test_the_store_is_the_core_event_log(tmp_path: Path) -> None:
    """No private Studio tables: one append-only log holds everything."""
    path = tmp_path / "odi.db"
    store = StudioMemory(str(path))
    _seed(store)

    connection = sqlite3.connect(path)
    try:
        tables = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        connection.close()
    assert "events" in tables
    assert "turns" not in tables
    assert "observations" not in tables


def test_the_file_store_is_open_for_concurrent_writers(tmp_path: Path) -> None:
    store = StudioMemory(str(tmp_path / "odi.db"))
    repo = store.service.repo
    assert isinstance(repo, SQLiteRepository)
    connection = repo.store.conn
    assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


# -- legacy import ---------------------------------------------------------


def _write_legacy_store(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL, role TEXT NOT NULL,
            content TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE observations (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, text TEXT NOT NULL,
            status TEXT NOT NULL, data TEXT NOT NULL, confidence REAL NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        INSERT INTO conversations VALUES ('c1', 'Old', 'now', 'now');
        INSERT INTO turns (conversation_id, role, content, created_at)
            VALUES ('c1', 'user', 'hello', 'now');
        INSERT INTO turns (conversation_id, role, content, created_at)
            VALUES ('c1', 'assistant', 'hi', 'now');
        INSERT INTO observations VALUES (
            'o1', 'nonsense-kind', 'Owns activation.', 'suggested',
            '{"job_id": "job-1"}', 0.7, 'now', 'now'
        );
        """
    )
    connection.commit()
    connection.close()


def test_a_pre_core_studio_database_is_imported_once(tmp_path: Path, monkeypatch) -> None:
    legacy = tmp_path / "studio.db"
    _write_legacy_store(legacy)
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_DB", str(legacy))
    path = str(tmp_path / "odi.db")

    store = StudioMemory(path)

    conversation = store.get_conversation("c1")
    assert conversation is not None
    assert conversation.title == "Old"
    assert [turn.content for turn in store.list_turns("c1")] == ["hello", "hi"]
    observation = store.list_observations(include_dismissed=True)[0]
    assert observation.category == "other"
    assert observation.status == "proposed"
    assert observation.data == {"job_id": "job-1"}
    assert observation.confidence == 0.7
    # The old file is renamed, never deleted: undo stays possible.
    assert not legacy.exists()
    assert Path(str(legacy) + ".imported").is_file()

    assert len(StudioMemory(path).list_observations(include_dismissed=True)) == 1


# -- observations ----------------------------------------------------------


def test_add_observation_defaults_to_proposed(memory: StudioMemory) -> None:
    observation = memory.add_observation("career", "Wants to be known for activation.")
    assert observation.status == "proposed"
    assert observation.confidence == 0.5
    assert observation.data == {}
    assert memory.list_observations() == [observation]


def test_observation_categories_are_validated(memory: StudioMemory) -> None:
    with pytest.raises(ValueError):
        memory.add_observation("nonsense", "text")
    assert "career" in OBSERVATION_CATEGORIES
    assert "customer" in OBSERVATION_CATEGORIES


def test_observation_text_must_be_present(memory: StudioMemory) -> None:
    with pytest.raises(ValueError):
        memory.add_observation("career", "   ")


def test_long_observation_text_is_trimmed_to_the_model_limit(memory: StudioMemory) -> None:
    observation = memory.add_observation("career", "x" * 400)
    assert len(observation.text) == 300


def test_observation_links_back_to_the_turn_that_produced_it(memory: StudioMemory) -> None:
    conversation_id = _seed(memory)
    observation = memory.add_observation(
        "customer",
        "Trials stall in onboarding.",
        conversation_id=conversation_id,
        source_message_id="m-2",
    )
    assert observation.conversation_id == conversation_id
    assert observation.source_message_id == "m-2"


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


# -- prompt context --------------------------------------------------------


def test_only_confirmed_memory_reaches_the_prompt(memory: StudioMemory) -> None:
    memory.add_observation("career", "Owns activation.", status="confirmed")
    memory.add_observation("constraint", "Legal review is slow.")

    context = memory.memory_context()
    assert "Owns activation." in context
    assert "Legal review is slow." not in context


def test_a_dismissed_observation_is_never_injected_again(memory: StudioMemory) -> None:
    dropped = memory.add_observation("business", "Ignore this.", status="confirmed")
    assert "Ignore this." in memory.memory_context()

    memory.update_observation(dropped.id, status="dismissed")
    assert "Ignore this." not in memory.memory_context()


def test_memory_context_is_empty_without_confirmed_facts(memory: StudioMemory) -> None:
    memory.add_observation("career", "a guess")
    assert memory.memory_context() == ""


def test_memory_context_is_bounded(memory: StudioMemory) -> None:
    for index in range(60):
        memory.add_observation(
            "evidence", f"confirmed fact {index} " + "y" * 250, status="confirmed"
        )

    context = memory.memory_context()
    assert len(context) <= MAX_CONTEXT_CHARS
    # Newest first: the block keeps the facts the person confirmed most recently.
    assert "confirmed fact 59" in context
    assert "confirmed fact 0" not in context


# -- brief and clearing ----------------------------------------------------


def test_the_brief_is_shared_with_the_core_store(memory: StudioMemory) -> None:
    saved = memory.save_brief({"product_name": "Trailmark", "job_statement": "Ship on time"})
    assert saved.product_name == "Trailmark"
    assert memory.get_brief() == saved


def test_clear_memory_removes_conversations_and_observations(memory: StudioMemory) -> None:
    conversation_id = _seed(memory)
    memory.add_observation("career", "Owns activation.")

    memory.clear_memory()

    assert memory.latest_conversation() is None
    assert memory.list_observations() == []
    with pytest.raises(ConversationNotFoundError):
        memory.list_turns(conversation_id)


# -- paths -----------------------------------------------------------------


def test_default_db_path_prefers_environment(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "studio.db"
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_DB", str(target))
    assert default_db_path() == target


def test_default_db_path_falls_back_to_home(monkeypatch) -> None:
    monkeypatch.delenv("AGENTIC_ODI_STUDIO_DB", raising=False)
    assert default_db_path().name == "studio.db"
    assert default_db_path().parent.name == ".agentic-odi"


def test_legacy_rows_are_read_as_a_linear_chain(tmp_path: Path, monkeypatch) -> None:
    legacy = tmp_path / "studio.db"
    _write_legacy_store(legacy)
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_DB", str(legacy))

    memory = StudioMemory(str(tmp_path / "odi.db"))
    turns = memory.conversation_tree("c1")

    assert [(turn.id, turn.parent_id) for turn in turns] == [
        ("c1-turn-1", None),
        ("c1-turn-2", "c1-turn-1"),
    ]


def test_untitled_legacy_threads_take_their_name_from_the_first_turn(
    tmp_path: Path, monkeypatch
) -> None:
    legacy = tmp_path / "studio.db"
    connection = sqlite3.connect(legacy)
    connection.executescript(
        """
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL, role TEXT NOT NULL,
            content TEXT NOT NULL, created_at TEXT NOT NULL
        );
        INSERT INTO conversations VALUES ('c1', '', 'now', 'now');
        INSERT INTO turns (conversation_id, role, content, created_at)
            VALUES ('c1', 'user', 'activation is stuck', 'now');
        """
    )
    connection.commit()
    connection.close()
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_DB", str(legacy))

    memory = StudioMemory(str(tmp_path / "odi.db"))

    assert memory.get_conversation("c1").title == "activation is stuck"  # type: ignore[union-attr]


def test_the_facade_types_match_the_core_entities(memory: StudioMemory) -> None:
    conversation = memory.create_conversation()
    memory.append_turn(conversation.id, "user", "hello", "m-1")
    assert isinstance(memory.get_conversation(conversation.id), Conversation)
    assert isinstance(memory.add_observation("career", "text"), Observation)
