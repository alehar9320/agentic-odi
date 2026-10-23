"""Conversational helper with offline fallbacks and a streaming tool loop.

Ported 1:1 from the Streamlit Living Studio app, upgraded to stream over SSE.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastmcp import Client as McpClient
from openai import AsyncOpenAI

from agentic_odi_studio_api.studio.probes import check_llm_health
from agentic_odi_studio_api.studio.schemas import ChatRequest, StudioBrief

SYSTEM_PROMPT = """You are Steve Jobs and an elite Outcome-Driven Innovation (ODI) strategist assisting a Product Manager in The Living Studio.
Your mission is to eliminate backlog paper-pushing and help the PM think exclusively in human intent, customer friction, and measurable outcomes.
Key principles:
1. Always start with the Job-to-be-Done (JTBD): "What is the core functional human job?"
2. Uncover Desired Outcomes using the strict ODI format: [Direction] + [Unit of Measure] + [Object of Control] + [Contextual Clarifier]. (e.g. "Minimize the time it takes to propagate secrets across environments").
3. Opportunity Score = Importance + max(Importance - Satisfaction, 0). Scores > 10 represent breakthrough underserved market opportunities.
4. When asked to add or query Jobs, Steps, or Outcomes, ALWAYS invoke the corresponding tools.
5. Embody clarity, focus, and causality. Strip away corporate jargon.
6. Continuously infer and refine the domain's V2MOM (Vision, Values, Methods, Obstacles, Measures) from conversational context as the user expresses what they are envisioning. Dynamically pick up new elements and ask targeted questions when needed to learn more about missing or ambiguous V2MOM artifacts."""


def _brief_lines(brief: StudioBrief | None) -> list[str]:
    if brief is None:
        return []
    facts = [
        ("Product", brief.product_name),
        ("Product URL", brief.product_url),
        ("Who it serves", brief.target_user),
        ("Job to be done", brief.job_statement),
        ("Core problem", brief.core_problem),
    ]
    if brief.v2mom:
        if brief.v2mom.vision:
            facts.append(("Vision (V2MOM)", brief.v2mom.vision))
        if brief.v2mom.values:
            facts.append(("Values (V2MOM)", ", ".join(brief.v2mom.values)))
        if brief.v2mom.methods:
            facts.append(("Methods (V2MOM)", ", ".join(brief.v2mom.methods)))
        if brief.v2mom.obstacles:
            facts.append(("Obstacles (V2MOM)", ", ".join(brief.v2mom.obstacles)))
        if brief.v2mom.measures:
            facts.append(("Measures (V2MOM)", ", ".join(brief.v2mom.measures)))
    return [f"- {label}: {value}" for label, value in facts if value.strip()]


def _brief_block(brief: StudioBrief | None) -> str:
    lines = _brief_lines(brief)
    if not lines:
        return ""
    return (
        "\n\nThe user set this context during onboarding. Treat it as given and do not "
        "re-ask for it:\n" + "\n".join(lines)
    )


def offline_fallback(user_input: str, brief: StudioBrief | None = None) -> str:
    """Deterministic, honest guidance when no LLM backend is reachable.

    No fabricated customer data, no invented scores: the studio says what it can
    do by hand and points at the surface that does it.
    """
    lower_inp = user_input.lower()
    context = ""
    if brief is not None and brief.job_statement.strip():
        context = (
            f"\n\n**Working job:** {brief.job_statement.strip()}"
            if not brief.product_name.strip()
            else f"\n\n**{brief.product_name.strip()}** — {brief.job_statement.strip()}"
        )

    if "guideline" in lower_inp or "framework" in lower_inp or "stage" in lower_inp:
        return (
            "### ODI, stage by stage\n\n"
            "1. **Define the job** — the functional progress a person is trying to make.\n"
            "2. **Capture desired outcomes** — `[direction] + [unit of measure] + [object of control] + [context]`.\n"
            "3. **Score the opportunity** — `importance + max(importance - satisfaction, 0)`; above 10 is underserved.\n"
            "4. **Map the job** — Define, Locate, Prepare, Confirm, Execute, Monitor, Modify, Conclude.\n\n"
            "Type `/capture` to record an outcome, `/jobmap` to walk the phases, "
            "and `/landscape` to see what is underserved." + context
        )
    if "simulate" in lower_inp or "bet" in lower_inp or "impact" in lower_inp:
        return (
            "### Simulate the bet by hand\n\n"
            "Open **`/impact`** and pick the outcome you want to test. The simulation "
            "shows before/after friction; it no longer invents a result when no model "
            "is connected." + context
        )
    if "evidence" in lower_inp or "call" in lower_inp or "quote" in lower_inp:
        return (
            "### Evidence needs a source\n\n"
            "No connector is wired up, so there is no live transcript to quote. "
            "Capture the signal you already have in **`/capture`** — the evidence field "
            "is stored with the outcome." + context
        )
    return (
        "I can't reason about that right now — no model is reachable. "
        "The studio still works by hand:\n\n"
        "- `/start` — set or correct your context\n"
        "- `/capture` — record an outcome with importance and satisfaction\n"
        "- `/jobmap` — add or edit the steps of the job\n"
        "- `/landscape` — review what is underserved\n\n"
        "Type `/help` for every command, or point Settings at a local model to "
        "bring the assistant back." + context
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _to_openai_messages(request: ChatRequest) -> list[dict[str, Any]]:
    system_prompt = SYSTEM_PROMPT + _brief_block(request.brief)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for message in request.messages:
        messages.append({"role": message.role, "content": message.content})
    return messages


def _openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }
        for tool in mcp_tools
    ]


async def stream_chat(request: ChatRequest) -> AsyncIterator[str]:
    """Yield SSE frames: status, delta, tool, message, canvas_dirty."""
    yield _sse("status", {"phase": "health_check"})
    healthy, _message = await check_llm_health(request.base_url, request.api_key, request.model)

    last_user = next((m.content for m in reversed(request.messages) if m.role == "user"), "")

    if not healthy:
        yield _sse("status", {"phase": "offline"})
        reply = offline_fallback(last_user, request.brief)
        yield _sse("delta", {"text": reply})
        yield _sse("message", {"content": reply})
        return

    yield _sse("status", {"phase": "mcp_tools"})
    llm_client = AsyncOpenAI(base_url=request.base_url, api_key=request.api_key, timeout=15.0)

    async with McpClient(request.mcp_url) as mcp_client:
        mcp_tools = await mcp_client.list_tools()
        openai_tools = _openai_tools(mcp_tools)
        messages: list[Any] = _to_openai_messages(request)

        yield _sse("status", {"phase": "model"})
        stream: Any = await llm_client.chat.completions.create(  # type: ignore[call-overload]
            model=request.model,
            messages=messages,
            tools=openai_tools if openai_tools else None,
            tool_choice="auto" if openai_tools else None,
            stream=True,
        )

        buffered_text: list[str] = []
        tool_calls: dict[int, dict[str, str]] = {}

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                buffered_text.append(delta.content)
            for tool_call in delta.tool_calls or []:
                entry = tool_calls.setdefault(
                    tool_call.index, {"id": "", "name": "", "arguments": ""}
                )
                if tool_call.id:
                    entry["id"] = tool_call.id
                if tool_call.function is not None:
                    if tool_call.function.name:
                        entry["name"] = tool_call.function.name
                    if tool_call.function.arguments:
                        entry["arguments"] += tool_call.function.arguments

        if not tool_calls:
            content = "".join(buffered_text)
            if content:
                yield _sse("delta", {"text": content})
            yield _sse("message", {"content": content})
            return

        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": entry["id"],
                        "type": "function",
                        "function": {
                            "name": entry["name"],
                            "arguments": entry["arguments"] or "{}",
                        },
                    }
                    for entry in tool_calls.values()
                ],
            }
        )

        for entry in tool_calls.values():
            name = entry["name"]
            yield _sse("tool", {"name": name, "status": "start"})
            try:
                arguments = json.loads(entry["arguments"] or "{}")
            except json.JSONDecodeError:
                arguments = {}

            try:
                result = await mcp_client.call_tool(name, arguments)
                result_str = str(result)
                yield _sse("tool", {"name": name, "status": "ok", "preview": result_str[:280]})
            except Exception as exc:  # noqa: BLE001
                result_str = f"Error calling {name}: {exc}"
                yield _sse("tool", {"name": name, "status": "error", "preview": result_str})

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": entry["id"],
                    "name": name,
                    "content": result_str,
                }
            )

        yield _sse("canvas_dirty", {"value": True})

        final_stream: Any = await llm_client.chat.completions.create(
            model=request.model,
            messages=messages,
            stream=True,
        )
        final_parts: list[str] = []
        async for chunk in final_stream:
            delta = chunk.choices[0].delta
            if delta.content:
                final_parts.append(delta.content)
                yield _sse("delta", {"text": delta.content})

        yield _sse("message", {"content": "".join(final_parts)})


__all__ = ["SYSTEM_PROMPT", "offline_fallback", "stream_chat"]
