"""A thread outlives the browser, the process, and the branch it was left on."""

from __future__ import annotations

from typing import Any

import pytest
from agentic_odi_core import InMemoryRepository, ODIService
from agentic_odi_core.services import ConversationNotFoundError
from agentic_odi_core.sqlite_repository import SQLiteRepository

PARTS: list[dict[str, Any]] = [
    {"kind": "text", "text": "Two things. "},
    {"kind": "ui", "id": "u-1", "node": {"type": "list", "props": {"items": ["Ship faster"]}}},
    {"kind": "tool", "id": "t-1", "name": "add_job", "status": "ok"},
]


def _sqlite(tmp_path) -> SQLiteRepository:
    return SQLiteRepository(str(tmp_path / "odi.db"), device_id="device-a")


@pytest.fixture(params=["memory", "sqlite"])
def service(request, tmp_path) -> ODIService:
    repo = InMemoryRepository() if request.param == "memory" else _sqlite(tmp_path)
    return ODIService(repo)


def test_a_new_thread_is_empty_and_untitled(service: ODIService) -> None:
    conversation = service.start_conversation()

    assert conversation.title is None
    assert conversation.head_id is None
    assert conversation.archived is False
    assert service.conversation_thread(conversation.id) == []


def test_the_first_thing_said_names_the_thread(service: ODIService) -> None:
    conversation = service.start_conversation()
    service.append_message(conversation.id, "user", "I own activation.\nAnd retention too.")

    assert service.get_conversation(conversation.id).title == "I own activation."


def test_an_answer_never_names_an_untitled_thread(service: ODIService) -> None:
    conversation = service.start_conversation()
    service.append_message(conversation.id, "assistant", "Sure.")

    assert service.get_conversation(conversation.id).title is None


def test_a_long_first_line_is_cut_to_a_title(service: ODIService) -> None:
    conversation = service.start_conversation()
    service.append_message(conversation.id, "user", "n" * 200)

    assert len(service.get_conversation(conversation.id).title or "") == 80


def test_turns_keep_the_ids_and_parents_the_client_sent(service: ODIService) -> None:
    conversation = service.start_conversation()
    question = service.append_message(conversation.id, "user", "list jobs", message_id="m-1")
    service.append_message(
        conversation.id, "assistant", "here they are", message_id="m-2", parent_id=question.id
    )

    thread = service.conversation_thread(conversation.id)
    assert [(message.id, message.parent_id) for message in thread] == [
        ("m-1", None),
        ("m-2", "m-1"),
    ]
    assert question.conversation_id == conversation.id


def test_the_head_follows_the_newest_turn(service: ODIService) -> None:
    conversation = service.start_conversation()
    first = service.append_message(conversation.id, "user", "one")
    second = service.append_message(conversation.id, "assistant", "two")

    assert service.get_conversation(conversation.id).head_id == second.id
    assert first.id != second.id


def test_a_second_answer_to_the_same_question_is_a_sibling(service: ODIService) -> None:
    conversation = service.start_conversation()
    question = service.append_message(conversation.id, "user", "which job first?")
    service.append_message(
        conversation.id, "assistant", "the billing one", message_id="a-1", parent_id=question.id
    )
    service.append_message(
        conversation.id, "assistant", "onboarding, surely", message_id="a-2", parent_id=question.id
    )

    parents = {
        message.id: message.parent_id for message in service.conversation_thread(conversation.id)
    }
    assert parents == {question.id: None, "a-1": question.id, "a-2": question.id}


def test_parts_come_back_in_order_verbatim(service: ODIService) -> None:
    conversation = service.start_conversation()
    service.append_message(conversation.id, "assistant", "Two things.", parts=PARTS)

    stored = service.conversation_thread(conversation.id)[0]
    assert [part["kind"] for part in stored.parts] == ["text", "ui", "tool"]
    assert stored.parts[1]["node"]["props"]["items"] == ["Ship faster"]
    assert stored.content == "Two things."


def test_a_thread_can_be_renamed_archived_and_deleted(service: ODIService) -> None:
    conversation = service.start_conversation()

    renamed = service.update_conversation(conversation.id, {"title": "Activation work"})
    assert renamed.title == "Activation work"

    archived = service.update_conversation(conversation.id, {"archived": True})
    assert archived.archived is True
    # Archiving is not deleting: the thread and its turns are still readable.
    assert service.get_conversation(conversation.id).id == conversation.id

    service.delete_conversation(conversation.id)
    with pytest.raises(ConversationNotFoundError):
        service.get_conversation(conversation.id)


def test_listing_newest_first_pages(service: ODIService) -> None:
    first = service.start_conversation()
    service.update_conversation(first.id, {"title": "first"})
    second = service.start_conversation()
    third = service.start_conversation()

    titles = [conversation.title for conversation in service.list_conversations()]
    assert titles[0] == third.title
    assert len(titles) == 3
    assert [c.id for c in service.list_conversations(limit=1, offset=1)] == [second.id]


def test_unknown_ids_are_a_typed_not_found(service: ODIService) -> None:
    for call in (
        lambda: service.get_conversation("nope"),
        lambda: service.conversation_thread("nope"),
        lambda: service.append_message("nope", "user", "hello"),
        lambda: service.update_conversation("nope", {"title": "x"}),
        lambda: service.delete_conversation("nope"),
    ):
        with pytest.raises(ConversationNotFoundError):
            call()


def test_a_reopen_reads_the_thread_it_wrote(tmp_path) -> None:
    """Nothing said is lost: a second store over the same file reads it all back."""
    writer = ODIService(_sqlite(tmp_path))
    conversation = writer.start_conversation()
    question = writer.append_message(conversation.id, "user", "Score this outcome.")
    answer = writer.append_message(
        conversation.id, "assistant", "Here is the card.", parts=PARTS, tokens_out=42
    )

    reader = ODIService(_sqlite(tmp_path))
    reopened = reader.get_conversation(conversation.id)
    thread = reader.conversation_thread(conversation.id)

    assert reopened.head_id == answer.id
    assert reopened.title == "Score this outcome."
    assert [message.id for message in thread] == [question.id, answer.id]
    assert thread[1].parts == PARTS
    assert thread[1].tokens_out == 42


def test_the_tail_of_a_long_thread_is_what_a_reload_needs(tmp_path) -> None:
    service = ODIService(_sqlite(tmp_path))
    conversation = service.start_conversation()
    for index in range(5):
        service.append_message(conversation.id, "user", f"turn {index}")

    tail = service.conversation_thread(conversation.id, limit=2)
    assert [message.content for message in tail] == ["turn 3", "turn 4"]

    before = service.conversation_thread(conversation.id, limit=2, before=tail[0].id)
    assert [message.content for message in before] == ["turn 1", "turn 2"]


def test_writes_carried_the_local_workspace_and_device(tmp_path) -> None:
    repo = SQLiteRepository(str(tmp_path / "odi.db"), workspace_id="acme", device_id="device-a")
    service = ODIService(repo)
    conversation = service.start_conversation()
    message = service.append_message(conversation.id, "user", "hello")
    observation = service.remember("I own activation.")

    assert conversation.workspace_id == "acme"
    assert conversation.device_id == "device-a"
    assert message.workspace_id == "acme"
    assert observation.workspace_id == "acme"


def test_the_default_workspace_is_local(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AGENTIC_ODI_WORKSPACE", raising=False)
    service = ODIService(_sqlite(tmp_path))
    conversation = service.start_conversation()
    observation = service.remember("Owns activation.")

    assert conversation.workspace_id == "local"
    assert observation.workspace_id == "local"
