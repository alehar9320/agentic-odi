"""Attachments become real model input, or an honest refusal."""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

from agentic_odi_studio_api.studio import chat
from agentic_odi_studio_api.studio.schemas import ChatAttachment, ChatMessage, ChatRequest

from test_studio_chat_branches import _events, _install


def _encoded(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _request(*messages: ChatMessage) -> ChatRequest:
    return ChatRequest(
        base_url="http://llm/v1",
        api_key="key",
        model="model",
        mcp_url="http://mcp",
        messages=list(messages),
    )


def _user(text: str, *attachments: ChatAttachment) -> ChatMessage:
    return ChatMessage(role="user", content=text, attachments=list(attachments))


def test_an_image_is_sent_as_image_content() -> None:
    image = ChatAttachment(
        name="screenshot.png", media_type="image/png", data=_encoded(b"\x89PNG bytes")
    )

    messages = chat._to_openai_messages(_request(_user("what is wrong here?", image)))

    user = messages[-1]
    assert user["role"] == "user"
    assert user["content"][0] == {"type": "text", "text": "what is wrong here?"}
    assert user["content"][1]["type"] == "image_url"
    assert user["content"][1]["image_url"]["url"] == f"data:image/png;base64,{image.data}"


def test_a_text_file_is_inlined_with_its_name() -> None:
    notes = ChatAttachment(
        name="interview.md",
        media_type="text/markdown",
        data=_encoded(b"We cannot find the config key.\n"),
    )

    messages = chat._to_openai_messages(_request(_user("summarise this", notes)))

    parts = messages[-1]["content"]
    assert parts[1]["type"] == "text"
    assert "[interview.md]" in parts[1]["text"]
    assert "We cannot find the config key." in parts[1]["text"]


def test_a_long_text_file_is_marked_as_truncated() -> None:
    long_file = ChatAttachment(
        name="log.txt",
        media_type="text/plain",
        data=_encoded(b"x" * (chat.MAX_INLINE_CHARS + 50)),
    )

    messages = chat._to_openai_messages(_request(_user("read this", long_file)))

    inline = messages[-1]["content"][1]["text"]
    assert "x" * chat.MAX_INLINE_CHARS in inline
    assert "truncated" in inline


def test_a_message_without_attachments_stays_plain() -> None:
    messages = chat._to_openai_messages(_request(_user("just words")))

    assert messages[-1] == {"role": "user", "content": "just words"}


def test_an_assistant_turn_never_claims_file_content() -> None:
    messages = chat._to_openai_messages(
        _request(
            ChatMessage(
                role="assistant",
                content="Looks like a config error.",
                attachments=[ChatAttachment(name="x.png", media_type="image/png", data="aGk=")],
            )
        )
    )

    assert messages[-1] == {"role": "assistant", "content": "Looks like a config error."}


def test_unreadable_files_are_refused_before_any_model_call(monkeypatch) -> None:
    _install(monkeypatch, [])
    pdf = ChatAttachment(name="deck.pdf", media_type="application/pdf", data=_encoded(b"%PDF"))

    frames = asyncio.run(_collect(_request(_user("read the deck", pdf))))

    events = _events(frames)
    assert "message" not in events
    failure = json.loads(events["error"][0])["error"]
    assert failure["code"] == "validation"
    assert "deck.pdf" in failure["message"]
    assert "cannot read" in failure["message"]
    # The turn is refused, not remembered as a question that was answered.
    assert "conversation" not in events


def test_empty_and_malformed_attachments_are_refused() -> None:
    assert chat._attachment_problem(ChatAttachment(name="a.txt", media_type="text/plain", data=""))
    assert chat._attachment_problem(
        ChatAttachment(name="a.txt", media_type="text/plain", data="not base64!!")
    )
    assert chat._attachment_problem(ChatAttachment(name="a", media_type="", data="aGk="))


def test_binary_masquerading_as_text_is_refused() -> None:
    latin1 = ChatAttachment(name="a.txt", media_type="text/plain", data=_encoded(b"\xff\xfe\x00"))

    assert "UTF-8" in (chat._attachment_problem(latin1) or "")


def test_oversized_files_are_refused() -> None:
    huge = ChatAttachment(
        name="big.txt",
        media_type="text/plain",
        data=_encoded(b"y" * (chat.MAX_ATTACHMENT_BYTES + 1)),
    )

    problem = chat._attachment_problem(huge) or ""
    assert "larger than" in problem


def test_the_remembered_turn_keeps_the_file_names() -> None:
    message = _user(
        "what do you make of this?",
        ChatAttachment(name="screenshot.png", media_type="image/png", data="aGk="),
        ChatAttachment(name="notes.md", media_type="text/markdown", data="aGk="),
    )

    stored = chat._stored_user_text(message)

    assert stored.startswith("what do you make of this?")
    assert "screenshot.png" in stored
    assert "notes.md" in stored


async def _collect(request: ChatRequest) -> list[str]:
    return [frame async for frame in chat.stream_chat(request)]


def test_an_attached_turn_still_streams_a_reply(monkeypatch) -> None:
    from test_studio_chat_branches import _FakeStream, _chunk

    _install(monkeypatch, [_FakeStream([_chunk("It is a config error.")])])
    image: Any = ChatAttachment(
        name="shot.png", media_type="image/png", data=_encoded(b"\x89PNG")
    )

    frames = asyncio.run(_collect(_request(_user("what is this?", image))))

    events = _events(frames)
    assert "message" in events
    assert "It is a config error." in events["message"][0]
