"""Conversational helper with offline fallbacks and a streaming tool loop.

Ported 1:1 from the Streamlit Living Studio app, upgraded to stream over SSE.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastmcp import Client as McpClient
from openai import AsyncOpenAI

from local_server.studio.probes import check_llm_health
from local_server.studio.schemas import ChatRequest

SYSTEM_PROMPT = """You are Steve Jobs and an elite Outcome-Driven Innovation (ODI) strategist assisting a Product Manager in The Living Studio.
Your mission is to eliminate backlog paper-pushing and help the PM think exclusively in human intent, customer friction, and measurable outcomes.
Key principles:
1. Always start with the Job-to-be-Done (JTBD): "What is the core functional human job?"
2. Uncover Desired Outcomes using the strict ODI format: [Direction] + [Unit of Measure] + [Object of Control] + [Contextual Clarifier]. (e.g. "Minimize the time it takes to propagate secrets across environments").
3. Opportunity Score = Importance + max(Importance - Satisfaction, 0). Scores > 10 represent breakthrough underserved market opportunities.
4. When asked to add or query Jobs, Steps, or Outcomes, ALWAYS invoke the corresponding tools.
5. Embody clarity, focus, and causality. Strip away corporate jargon."""


def offline_fallback(user_input: str) -> str:
    """Intelligent grounded fallback when no LLM backend is reachable."""
    lower_inp = user_input.lower()
    if "guideline" in lower_inp or "framework" in lower_inp or "stage" in lower_inp:
        return (
            "### 📖 Outcome-Driven Innovation (ODI) Process Guidelines\n\n"
            "1. **Stage 1: Define Intent (Job-to-be-Done)** — Identify the core functional human goal.\n"
            "2. **Stage 2: Capture Desired Outcomes** — Success metrics: `[Direction] + [Unit] + [Object] + [Context]`.\n"
            "3. **Stage 3: Opportunity Scoring** — `Importance + max(Importance - Satisfaction, 0)`. Focus on scores > 10.\n"
            "4. **Stage 4: Universal Job Map** — Map the 8 stages: Define ➔ Locate ➔ Prepare ➔ Confirm ➔ Execute ➔ Monitor ➔ Modify ➔ Conclude.\n\n"
            "*(Connected in Local Studio Mode. Start your local LLM backend at `http://localhost:8001/v1` for full autonomous completions)*"
        )
    if "simulate" in lower_inp or "bet" in lower_inp or "impact" in lower_inp:
        return (
            "### ⚡ WYSIWYG Impact Simulation Result\n\n"
            "- **Target Outcome**: O-1 (*Minimize time taken to propagate secrets*)\n"
            "- **Proposed Bet**: Automated Secret Sync Daemon\n"
            "- **Before**: 45 minutes of manual copy-paste across 400 developer pipelines.\n"
            "- **After**: Under 30 seconds ambient zero-touch sync.\n"
            "- **Time-to-Value Shift**: **-90% friction reduction**.\n"
            "- **Human Impact**: 3,000 hours of developer agony eliminated every month. Build it."
        )
    if "evidence" in lower_inp or "call" in lower_inp or "quote" in lower_inp:
        return (
            "### 🔍 Causal Lineage: Real-Time Evidence\n\n"
            "- **Signal Source**: Gong Call #104 (Enterprise Team Alpha)\n"
            "- **Customer Voice**: *'We lost two hours on deploy day because someone missed a database config key.'*\n"
            "- **Telemetry**: 400 microservices impacted weekly; 14% failed build rate attributed to config drift."
        )
    return (
        f'I received your intent: **"{user_input}"**.\n\n'
        "In The Living Studio, every idea is evaluated against human outcomes rather than story points. "
        "Notice how our highest opportunity outcome (`O-1: Minimize propagation time`) has an **Opportunity Score of 15.3**, "
        "signaling severe market underservice. Tap **'Simulate Impact'** on the canvas or type `Simulate Auto-Sync Bet` to test causality."
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _to_openai_messages(request: ChatRequest) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
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
        reply = offline_fallback(last_user)
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
