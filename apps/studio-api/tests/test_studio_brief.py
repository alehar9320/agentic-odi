"""The user's onboarding context must reach the model and the offline fallback."""

from __future__ import annotations

import asyncio
import json

from agentic_odi_studio_api.studio import chat
from agentic_odi_studio_api.studio.schemas import ChatMessage, ChatRequest, StudioBrief

BRIEF = StudioBrief(
    product_name="Ambient",
    target_user="Platform engineers",
    job_statement="Get a service from commit to production",
    core_problem="A missed config key costs hours",
)


def _request(brief: StudioBrief | None = BRIEF) -> ChatRequest:
    return ChatRequest(
        base_url="http://llm/v1",
        model="model",
        mcp_url="http://mcp",
        messages=[ChatMessage(role="user", content="what next?")],
        brief=brief,
    )


def test_system_prompt_carries_the_brief() -> None:
    messages = chat._to_openai_messages(_request())

    system = messages[0]["content"]
    assert "Ambient" in system
    assert "Platform engineers" in system
    assert "Get a service from commit to production" in system


def test_system_prompt_is_unchanged_without_a_brief() -> None:
    messages = chat._to_openai_messages(_request(None))

    assert messages[0]["content"] == chat.SYSTEM_PROMPT


def test_offline_fallback_is_grounded_and_actionable() -> None:
    reply = chat.offline_fallback("what should I do next?", BRIEF)

    assert "Get a service from commit to production" in reply
    assert "/capture" in reply
    assert "15.3" not in reply  # no fabricated demo score


def test_offline_stream_is_tagged_so_the_ui_can_label_it(monkeypatch) -> None:
    async def _unhealthy(*args, **kwargs):
        return False, "offline"

    monkeypatch.setattr(chat, "check_llm_health", _unhealthy)

    async def _collect() -> list[str]:
        return [frame async for frame in chat.stream_chat(_request())]

    frames = asyncio.run(_collect())
    phases = [
        json.loads(frame.split("data: ", 1)[1])["phase"]
        for frame in frames
        if "event: status" in frame
    ]
    assert "offline" in phases
