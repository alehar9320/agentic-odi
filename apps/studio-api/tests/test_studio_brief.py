"""The user's onboarding context must reach the model and the offline fallback."""

from __future__ import annotations

import asyncio
import json

from agentic_odi_studio_api.studio import chat
from agentic_odi_studio_api.studio.schemas import V2MOM, ChatMessage, ChatRequest, StudioBrief

BRIEF = StudioBrief(
    product_name="Ambient",
    target_user="Platform engineers",
    job_statement="Get a service from commit to production",
    core_problem="A missed config key costs hours",
    v2mom=V2MOM(
        vision="Zero friction deploys",
        values=["Speed", "Security"],
        methods=["Automate checks"],
        obstacles=["Legacy pipelines"],
        measures=["Deploy time < 5m"],
    ),
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


def test_system_prompt_carries_the_v2mom() -> None:
    messages = chat._to_openai_messages(_request())

    system = messages[0]["content"]
    assert "Zero friction deploys" in system
    assert "Speed, Security" in system
    assert "Automate checks" in system
    assert "Legacy pipelines" in system
    assert "Deploy time < 5m" in system


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


def _store_client():
    from agentic_odi_core import InMemoryRepository
    from agentic_odi_studio_api.app import create_app
    from fastapi.testclient import TestClient

    return TestClient(create_app(InMemoryRepository()))


def test_the_stored_brief_keeps_the_v2mom() -> None:
    """The vision is captured in a conversation, so it has to survive the round trip."""
    client = _store_client()
    payload = {
        "product_name": "Ambient",
        "target_user": "Platform engineers",
        "job_statement": "Get a service from commit to production",
        "core_problem": "A missed config key costs hours",
        "v2mom": {"vision": "Zero friction deploys", "values": ["Speed"]},
    }

    saved = client.put("/api/brief", json=payload).json()["brief"]

    assert saved["v2mom"]["vision"] == "Zero friction deploys"
    reread = client.get("/api/brief").json()["brief"]
    assert reread["v2mom"]["values"] == ["Speed"]


def test_a_core_brief_carries_the_vision_into_the_prompt() -> None:
    """The sidecar reads the stored brief when the client sends none of its own."""
    from agentic_odi_core import Brief
    from agentic_odi_core.models import V2MOM as CoreV2MOM

    lines = chat._brief_lines(Brief(v2mom=CoreV2MOM(vision="Zero friction deploys")))

    assert any("Vision (V2MOM)" in line and "Zero friction deploys" in line for line in lines)
