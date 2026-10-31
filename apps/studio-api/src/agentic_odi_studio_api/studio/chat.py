"""Conversational helper with offline fallbacks and a streaming tool loop.

The loop fans the MCP tools and three local tools — ``render_ui``,
``remember``, and ``add_connector`` — into the completion. Local tools are
intercepted rather than forwarded: ``render_ui`` validates its spec against the
catalog the client sent and streams a ``ui`` event, ``remember`` stores a
suggested observation and streams a ``memory`` event, and ``add_connector``
writes the shared connector registry and streams a ``connector`` event.

The conversation is persisted when a memory store is supplied, so a PM can leave
and come back to the same thread and the same working context.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

from agentic_odi_core import ModelRouter, ModelTier, ODIService, RoutingMode
from agentic_odi_core.remote import (
    StudioError,
    StudioErrorCode,
    parse_tool_result,
    tool_result_text,
)
from fastmcp import Client as McpClient
from openai import AsyncOpenAI

from agentic_odi_studio_api.studio.approvals import (
    ApprovalRegistry,
    wait_for_decision,
)
from agentic_odi_studio_api.studio.claims import (
    Claim,
    EvidenceIndex,
    EvidenceSnapshot,
    split_claims,
)
from agentic_odi_studio_api.studio.connectors import ConnectorService
from agentic_odi_studio_api.studio.memory import OBSERVATION_KINDS, StudioMemory
from agentic_odi_studio_api.studio.observability import log_turn
from agentic_odi_studio_api.studio.probes import check_llm_health, is_endpoint_reachable
from agentic_odi_studio_api.studio.schemas import (
    AttachmentRef,
    ChatMessage,
    ChatRequest,
    StudioBrief,
)
from agentic_odi_studio_api.studio.ui_spec import RENDER_UI_TOOL, UiCatalog

log = logging.getLogger(__name__)

#: A rejected surface is corrected in the same reply, but a model that keeps
#: missing must not be able to loop forever.
MAX_TOOL_ROUNDS = 3

#: Tool names that change stored data. Everything else is a read, a surface, or
#: a memory note — none of which needs a confirmation the user would learn to
#: click through.
MUTATING_TOOL_PREFIXES: tuple[str, ...] = (
    "add_",
    "create_",
    "update_",
    "delete_",
    "ingest_",
    "remove_",
)

#: Writes whose names do not follow the verb-prefix convention.
MUTATING_TOOLS: frozenset[str] = frozenset(
    {"promote_evidence", "segment_market", "propose_strategy"}
)

#: Attachments are context, not a corpus: five files, and a bounded slice of each.
MAX_ATTACHMENTS = 5
MAX_ATTACHMENT_TEXT = 20_000

#: A single tool result is summarized for the source chip, never quoted whole.
MAX_SOURCE_PREVIEW = 160


def is_mutating_tool(name: str) -> bool:
    """Whether a tool call changes stored data and should be confirmed."""
    return name in MUTATING_TOOLS or name.startswith(MUTATING_TOOL_PREFIXES)


SYSTEM_PROMPT = """You are an elite product strategist working inside The Living Studio, a room built for product managers.
Your job is to help the PM choose and win the next opportunity that matters — to customers, the business, and their career.
Outcome-Driven Innovation (ODI) is your private engine, not the conversation. Translate the PM's ambition into jobs, outcomes, and evidence silently, and speak in the PM's language.

How to work:
1. Start with the person and the stakes. Ask what opportunity they are chasing, who it is for, and what winning would change. One good question at a time.
2. Mirror their words back, then offer a sharp hypothesis they can correct.
3. When they give you context worth keeping — a career goal, a constraint, a stakeholder, a belief — call `remember` with the smallest useful observation. Do not ask permission first; the UI lets them confirm, edit, or dismiss it.
4. Use ODI when it earns its keep: a job statement clarifies, a desired outcome sharpens, an opportunity score compares. Never lead with the framework or lecture about stages.
5. Opportunity Score = Importance + max(Importance - Satisfaction, 0). Above 10 means underserved.
6. When a surface carries the evidence better than a paragraph, call `render_ui` once, then write one short sentence. Never describe in prose what a card can already show.
7. The conversation is the product: every surface you render lands in the thread the PM is already reading. Never tell them to open a panel, a tab, or a view to see something you can show inline.
8. Capture and simulation are conversations, not forms: ask for the customer's words or the bet in plain language, render the card that carries it, and offer the next move as an action on that card.
9. When asked to add or query Jobs, Steps, or Outcomes, ALWAYS invoke the corresponding tools.
10. "Who is this for?" is answered by segments, not by demographics: call `get_segments`, and if none are recorded yet, `segment_market` first. "So what do we do?" is answered by `propose_strategy`, which names the paths it beat — say what those were and why. Never present a verdict without the confidence behind it.
11. Be warm, direct, and specific. Short sentences. No corporate jargon, no therapy-speak, no emojis.
12. Every declarative sentence you write ends with an evidence marker: `[[ev:<id>]]`, `[[ev:<id>,<id>]]` (at most three), or `[[hypothesis]]` when no record supports it. Questions, instructions, headings, and code carry no marker.
13. Never invent an evidence id. Cite only ids a tool returned in this turn; anything else is shown as unsupported and your sentence is underlined as uncited.
14. Before any claim about what customers said, did, or want, call `list_evidence` (or `get_evidence`) and cite the record it returns.
15. Put the marker at the very end of the sentence, outside code. One marker supports one sentence, never the sentence beside it."""


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


class _TurnFailure(Exception):
    """A fatal failure that ends the turn with one ``error`` event."""

    def __init__(self, error: StudioError) -> None:
        self.error = error
        super().__init__(error.message)


def _error_frame(problem: StudioError, request_id: str) -> str:
    """Render the terminal ``error`` event for a fatal turn failure."""
    body = problem.model_copy(update={"request_id": request_id or problem.request_id})
    return _sse("error", {"error": body.model_dump(mode="json"), "request_id": request_id})


def _attachment_block(attachments: list[AttachmentRef]) -> str:
    """The readable part of the user's attachments, bounded and labelled."""
    blocks: list[str] = []
    for attachment in attachments[:MAX_ATTACHMENTS]:
        text = (attachment.text or "").strip()
        if not text:
            continue
        blocks.append(
            f"[Attached file: {attachment.name}]\n{text[:MAX_ATTACHMENT_TEXT]}\n[/Attached file]"
        )
    return "\n\n".join(blocks)


def _image_parts(attachments: list[AttachmentRef]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for attachment in attachments[:MAX_ATTACHMENTS]:
        if attachment.data_url and attachment.content_type.startswith("image/"):
            parts.append({"type": "image_url", "image_url": {"url": attachment.data_url}})
    return parts


def _user_content(message: ChatMessage, attachments: list[AttachmentRef]) -> Any:
    """Text plus any readable attachments, shaped for an OpenAI-compatible model."""
    block = _attachment_block(attachments)
    text = f"{message.content}\n\n{block}".strip() if block else message.content
    images = _image_parts(attachments)
    if not images:
        return text
    return [{"type": "text", "text": text}, *images]


def _to_openai_messages(request: ChatRequest, memory_context: str = "") -> list[dict[str, Any]]:
    system_prompt = SYSTEM_PROMPT + _brief_block(request.brief)
    if memory_context:
        system_prompt += "\n\n" + memory_context
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    last_user = next((m for m in reversed(request.messages) if m.role == "user"), None)
    for message in request.messages:
        if message is last_user and request.attachments:
            messages.append(
                {"role": "user", "content": _user_content(message, request.attachments)}
            )
        else:
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


ADD_CONNECTOR_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "add_connector",
        "description": (
            "Register an external MCP or REST connector into the shared connector "
            "registry so the Living Studio and CLI can use it. Provide a 'preset' "
            "id (from connectors catalog) and optionally a 'name' and 'url' "
            "override, or a custom 'name' + 'url'. Does not require an MCP server."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Unique connector name (defaults to the preset id).",
                },
                "preset": {
                    "type": "string",
                    "description": "Preset id, e.g. notion, posthog, exa, linear, github.",
                },
                "url": {
                    "type": "string",
                    "description": "Custom endpoint URL (used when no preset is given).",
                },
            },
        },
    },
}


REMEMBER_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "remember",
        "description": (
            "Save one durable observation about the product manager or their work so "
            "you can use it in later conversations: a career goal, the opportunity "
            "they are chasing, a business constraint, a stakeholder, a piece of "
            "evidence, or a working preference. Send the smallest useful sentence. "
            "The PM will see it in 'What I've learned' and can confirm, edit, or "
            "dismiss it. Do not call this for transient details of the current task."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": sorted(OBSERVATION_KINDS),
                    "description": "The area of context this observation belongs to.",
                },
                "text": {
                    "type": "string",
                    "description": "One plain-language sentence in the PM's own terms.",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "How sure you are. Defaults to 0.6.",
                },
                "data": {
                    "type": "object",
                    "description": "Optional structured details, such as a job id.",
                },
            },
            "required": ["kind", "text"],
        },
    },
}


def _apply_add_connector(
    arguments: dict[str, Any], service: ConnectorService
) -> tuple[str, list[dict[str, Any]]]:
    """Register a connector locally and return SSE event dicts for the stream."""
    name = arguments.get("name")
    preset_id = arguments.get("preset")
    url = arguments.get("url")
    try:
        config = service.add(name=name, preset_id=preset_id, url=url)
    except Exception as exc:  # noqa: BLE001
        event = {"event": "connector", "data": {"status": "error", "error": str(exc)}}
        return f"Error: {exc}", [event]
    event_data: dict[str, Any] = {"action": "registered", "name": config.name}
    if preset_id is not None:
        event_data["preset"] = preset_id
    if url is not None:
        event_data["url"] = url
    return f"registered connector {config.name}", [{"event": "connector", "data": event_data}]


def _apply_remember(
    arguments: dict[str, Any], memory: StudioMemory | None
) -> tuple[str, dict[str, Any] | None]:
    """Store one suggested observation without asking the PM first."""
    if memory is None:
        return "Memory is not available to this client.", None

    kind = str(arguments.get("kind", ""))
    text = str(arguments.get("text", ""))
    data = arguments.get("data")
    try:
        confidence = float(arguments.get("confidence", 0.6))
    except (TypeError, ValueError):
        confidence = 0.6

    try:
        observation = memory.add_observation(
            kind=kind,
            text=text,
            data=data if isinstance(data, dict) else None,
            status="suggested",
            confidence=confidence,
        )
    except ValueError as exc:
        return f"Could not remember that: {exc}", None
    return "Saved for the user to review.", {"observation": observation.to_dict()}


def _render_ui_tool(catalog: UiCatalog) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": RENDER_UI_TOOL,
            "description": (
                "Render one rich surface inline in the conversation. Reach for this whenever a "
                "surface carries the evidence better than a paragraph: an opportunity thesis, "
                "an outcome with its scores, a ranked opportunity board, a before/after "
                "simulation of a bet, a customer quote, the eight-stage job map, or a decision "
                "record. Send one surface, then one short sentence.\n\n"
                "Catalog (* marks a required prop):\n" + catalog.describe()
            ),
            "parameters": catalog.tool_schema(),
        },
    }


def _local_tools(catalog: UiCatalog | None) -> list[dict[str, Any]]:
    tools = [_render_ui_tool(catalog)] if catalog is not None else []
    return [*tools, REMEMBER_TOOL, ADD_CONNECTOR_TOOL]


def _parse_arguments(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _collect_tool_calls(delta: Any, tool_calls: dict[int, dict[str, str]]) -> None:
    for tool_call in delta.tool_calls or []:
        entry = tool_calls.setdefault(tool_call.index, {"id": "", "name": "", "arguments": ""})
        if tool_call.id:
            entry["id"] = tool_call.id
        if tool_call.function is not None:
            if tool_call.function.name:
                entry["name"] = tool_call.function.name
            if tool_call.function.arguments:
                entry["arguments"] += tool_call.function.arguments


def _persist_turn(
    memory: StudioMemory | None,
    conversation_id: str | None,
    role: str,
    content: str,
    message_id: str | None = None,
    parent_id: str | None = None,
    claims: list[Claim] | None = None,
) -> int | None:
    """Record a turn and its claims, tolerating a duplicate retry.

    A retry that reuses a message id rewrites the same citation rows instead of
    stacking new ones. A failure to remember never breaks the reply.
    """
    if memory is None or conversation_id is None or not content.strip():
        return None
    try:
        turns = memory.list_turns(conversation_id)
        if message_id:
            existing = next((turn for turn in turns if turn.message_id == message_id), None)
            if existing is not None:
                if claims:
                    memory.add_citations(existing.id, claims)
                return existing.id
        if turns and turns[-1].role == role and turns[-1].content == content:
            if claims:
                memory.add_citations(turns[-1].id, claims)
            return turns[-1].id
        turn_id = memory.append_turn(conversation_id, role, content, message_id, parent_id)
        if claims:
            memory.add_citations(turn_id, claims)
        return turn_id
    except Exception:  # noqa: BLE001
        return None


def _reasoning_text(delta: Any) -> str:
    """The model's thinking, when the backend exposes it (vLLM, Ollama, DeepSeek)."""
    for attribute in ("reasoning_content", "reasoning"):
        value = getattr(delta, attribute, None)
        if isinstance(value, str) and value:
            return value
    return ""


def _approval_prompt(name: str, arguments: dict[str, Any]) -> str:
    human = name.replace("_", " ")
    return f"Allow the assistant to {human}?"


def _denial_result(name: str, decision: Any) -> str | None:
    """The tool result for a write that must not run, or ``None`` when it may.

    A declined or expired gate is never an error: the turn continues and the
    model may propose something else.
    """
    if decision is None:
        return (
            f"The approval request for {name} expired before the user answered. "
            "Nothing was changed. Ask the user whether to try again."
        )
    if decision.approved:
        return None
    reason = decision.reason.strip()
    detail = f" The user said: {reason}" if reason else ""
    return (
        f"The user declined to run {name}, so nothing was changed.{detail} "
        "Do not retry it without being asked."
    )


def _local_evidence_resolver(
    service: ODIService | None,
) -> Any:
    """Resolve an id from the local store, so the local backend validates too."""
    if service is None:
        return None

    def resolve(evidence_id: str) -> EvidenceSnapshot | None:
        try:
            record = service.get_evidence(evidence_id)
        except Exception:  # noqa: BLE001 - the store is optional context
            return None
        if record is None:
            return None
        return EvidenceSnapshot(id=record.id, name=record.name, source_name=record.source_name)

    return resolve


def _message_payload(content: str, claims: list[Claim]) -> dict[str, Any]:
    """The terminal frame: the prose, plus what each sentence stands behind."""
    payload: dict[str, Any] = {"content": content}
    if claims:
        payload["claims"] = [claim.to_dict() for claim in claims]
    return payload


def _source_frame(counters: dict[str, int], name: str, result: str) -> dict[str, Any]:
    """One provenance entry per tool the turn actually read."""
    counters["sources"] += 1
    preview = " ".join(result.split())[:MAX_SOURCE_PREVIEW]
    return {
        "event": "source",
        "data": {
            "id": f"src-{counters['sources']}",
            "title": f"{name} — {preview}" if preview else name,
            "filename": name,
            "mediaType": "application/json",
            "preview": preview,
        },
    }


def _routing_mode(value: str | None) -> RoutingMode:
    """Map the requested routing mode onto the router's modes."""
    try:
        return RoutingMode((value or RoutingMode.AUTO.value).strip().lower())
    except ValueError:
        return RoutingMode.AUTO


async def _turn_frames(
    request: ChatRequest,
    service: ConnectorService | None,
    memory: StudioMemory | None,
    request_id: str,
    counters: dict[str, int],
    approvals: ApprovalRegistry | None = None,
    local_service: ODIService | None = None,
) -> AsyncIterator[str]:
    """Yield the frames of one turn, raising ``_TurnFailure`` on a fatal error."""

    def frame(event: str, data: dict[str, Any]) -> str:
        return _sse(event, {**data, "request_id": request_id})

    yield frame("status", {"phase": "health_check"})

    last_user_message = next((m for m in reversed(request.messages) if m.role == "user"), None)
    last_user = last_user_message.content if last_user_message is not None else ""
    user_message_id = last_user_message.id if last_user_message is not None else None
    user_parent_id = last_user_message.parent_id if last_user_message is not None else None
    assistant_message_id = request.assistant_id

    conversation_id: str | None = None
    if memory is not None:
        conversation = (
            memory.get_conversation(request.conversation_id) if request.conversation_id else None
        )
        if conversation is None:
            conversation = memory.create_conversation()
        conversation_id = conversation.id
        _persist_turn(memory, conversation_id, "user", last_user, user_message_id, user_parent_id)
        updated = memory.get_conversation(conversation_id) or conversation
        yield frame("conversation", {"id": updated.id, "title": updated.title})

    healthy, _message = await check_llm_health(request.base_url, request.api_key, request.model)

    routing_mode = _routing_mode(request.routing_mode)
    router = ModelRouter(mode=routing_mode)
    target_tier = router.resolve_tier(remote_available=healthy)
    if target_tier == ModelTier.ON_DEVICE_LLM and routing_mode == RoutingMode.AUTO:
        # Automatic routing keeps the studio's own deterministic guidance as the
        # floor: honest, useful answers beat a placeholder model's guess.
        target_tier = ModelTier.RULE_BASED
    if target_tier == ModelTier.REMOTE_LLM and not healthy:
        # A forced remote tier still has to answer when the backend is down.
        target_tier = ModelTier.RULE_BASED

    if target_tier == ModelTier.RULE_BASED:
        yield frame("status", {"phase": "offline"})
        reply = offline_fallback(last_user, request.brief)
        yield frame("delta", {"text": reply})
        yield frame("message", {"content": reply})
        _persist_turn(
            memory,
            conversation_id,
            "assistant",
            reply,
            assistant_message_id,
            user_message_id,
        )
        return

    if target_tier == ModelTier.ON_DEVICE_LLM:
        yield frame("status", {"phase": "fallback_tier", "tier": target_tier.value})
        chunks: list[str] = []
        async for chunk in router.generate_fallback_stream(last_user, target_tier):
            chunks.append(chunk)
            yield frame("delta", {"text": chunk})
        reply = "".join(chunks)
        yield frame("message", {"content": reply})
        _persist_turn(
            memory,
            conversation_id,
            "assistant",
            reply,
            assistant_message_id,
            user_message_id,
        )
        return

    catalog = UiCatalog.from_manifest(
        request.ui_catalog.model_dump() if request.ui_catalog else None
    )

    # The probe is a blocking socket check: keep it off the event loop.
    mcp_reachable = await asyncio.to_thread(is_endpoint_reachable, request.mcp_url, 0.3)
    if not mcp_reachable:
        raise _TurnFailure(
            StudioError(
                code=StudioErrorCode.MCP_UNREACHABLE,
                message=f"MCP server unreachable at {request.mcp_url}",
                suggestion="Check that the MCP server is running, then try again.",
                retryable=True,
            )
        )

    yield frame("status", {"phase": "mcp_tools"})
    llm_client = AsyncOpenAI(base_url=request.base_url, api_key=request.api_key, timeout=15.0)
    connector_service = service if service is not None else ConnectorService()
    memory_context = memory.memory_context() if memory is not None else ""
    # Every id the turn actually received, with the label that came with it.
    evidence = EvidenceIndex(resolver=_local_evidence_resolver(local_service))

    async with AsyncExitStack() as stack:
        try:
            mcp_client = await stack.enter_async_context(McpClient(request.mcp_url))
            mcp_tools = await mcp_client.list_tools()
        except Exception as exc:  # noqa: BLE001
            # The reason stays in the log: the client gets the request id.
            log.exception("MCP server unavailable (request_id=%s)", request_id)
            raise _TurnFailure(
                StudioError(
                    code=StudioErrorCode.MCP_UNREACHABLE,
                    message="The MCP server is not serving tools.",
                    suggestion="Check that the MCP server is running, then try again.",
                    retryable=True,
                )
            ) from exc

        openai_tools = _openai_tools(mcp_tools) + _local_tools(catalog)
        messages: list[Any] = _to_openai_messages(request, memory_context)

        spoken: list[str] = []
        ui_count = 0
        canvas_dirty = False

        for _round in range(MAX_TOOL_ROUNDS):
            counters["rounds"] += 1
            yield frame("status", {"phase": "model"})
            try:
                stream: Any = await llm_client.chat.completions.create(  # type: ignore[call-overload]
                    model=request.model,
                    messages=messages,
                    tools=openai_tools if openai_tools else None,
                    tool_choice="auto" if openai_tools else None,
                    stream=True,
                )
            except Exception as exc:  # noqa: BLE001
                log.exception("The model could not be reached (request_id=%s)", request_id)
                raise _TurnFailure(
                    StudioError(
                        code=StudioErrorCode.LLM_UNREACHABLE,
                        message="The model could not be reached.",
                        suggestion="Check the model settings, then try again.",
                        retryable=True,
                    )
                ) from exc

            turn_text: list[str] = []
            tool_calls: dict[int, dict[str, str]] = {}

            try:
                async for chunk in stream:
                    delta = chunk.choices[0].delta
                    reasoning = _reasoning_text(delta)
                    if reasoning:
                        # Thinking is shown as a disclosure, and is never part of
                        # the answer or of the history that replays.
                        yield frame("reasoning", {"text": reasoning})
                    if delta.content:
                        # Prose renders as it is generated. A card that follows it
                        # simply comes after the sentence that introduces it.
                        turn_text.append(delta.content)
                        spoken.append(delta.content)
                        yield frame("delta", {"text": delta.content})
                    _collect_tool_calls(delta, tool_calls)
            except Exception as exc:  # noqa: BLE001
                log.exception("The model stopped responding (request_id=%s)", request_id)
                raise _TurnFailure(
                    StudioError(
                        code=StudioErrorCode.LLM_UNREACHABLE,
                        message="The model stopped responding.",
                        suggestion="Try again — your question is still here.",
                        retryable=True,
                    )
                ) from exc

            if not tool_calls:
                final = "".join(spoken)
                claims = split_claims(final, evidence)
                _persist_turn(
                    memory,
                    conversation_id,
                    "assistant",
                    final,
                    assistant_message_id,
                    user_message_id,
                    claims,
                )
                yield frame("message", _message_payload(final, claims))
                return

            messages.append(
                {
                    "role": "assistant",
                    "content": "".join(turn_text) or None,
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
                arguments = _parse_arguments(entry["arguments"])
                counters["tool_calls"] += 1

                declined: str | None = None
                if request.approvals and approvals is not None and is_mutating_tool(name):
                    approval, future = approvals.open(
                        tool_call_id=entry["id"],
                        name=name,
                        arguments=arguments,
                        prompt=_approval_prompt(name, arguments),
                    )
                    # The gate is announced before it is awaited: the client
                    # cannot answer a question it was never sent.
                    yield frame("approval", approval.to_dict())
                    decision = await wait_for_decision(approvals, approval, future)
                    declined = _denial_result(name, decision)

                if declined is not None:
                    counters["tool_errors"] += 1
                    result_str = declined
                    yield frame("tool", {"name": name, "status": "declined", "preview": declined})
                elif name == "add_connector":
                    yield frame("tool", {"name": name, "status": "start"})
                    result_str, events = _apply_add_connector(arguments, connector_service)
                    for event in events:
                        yield frame(event["event"], event["data"])
                    if result_str.startswith("Error:"):
                        counters["tool_errors"] += 1
                        yield frame(
                            "tool", {"name": name, "status": "error", "preview": result_str}
                        )
                    else:
                        yield frame("tool", {"name": name, "status": "ok"})
                elif name == "remember":
                    yield frame("tool", {"name": name, "status": "start"})
                    result_str, memory_event = _apply_remember(arguments, memory)
                    if memory_event is None:
                        counters["tool_errors"] += 1
                        yield frame(
                            "tool", {"name": name, "status": "error", "preview": result_str}
                        )
                    else:
                        yield frame("tool", {"name": name, "status": "ok"})
                        yield frame("memory", memory_event)
                else:
                    yield frame("tool", {"name": name, "status": "start"})
                    if name == RENDER_UI_TOOL:
                        if catalog is None:
                            result_str = (
                                "UI is not available to this client. Answer in prose instead."
                            )
                            counters["tool_errors"] += 1
                            yield frame(
                                "tool", {"name": name, "status": "error", "preview": result_str}
                            )
                        else:
                            problem = catalog.validate(arguments)
                            if problem:
                                result_str = (
                                    f"UI rejected: {problem}. Nothing was shown to the user. "
                                    "Fix it and try once more."
                                )
                                counters["tool_errors"] += 1
                                yield frame(
                                    "tool", {"name": name, "status": "error", "preview": problem}
                                )
                            else:
                                ui_count += 1
                                result_str = "Rendered inline for the user."
                                yield frame("tool", {"name": name, "status": "ok"})
                                yield frame("ui", {"id": f"ui-{ui_count}", "spec": arguments})
                    else:
                        try:
                            result = await mcp_client.call_tool(name, arguments)
                            result_str = tool_result_text(result)
                        except Exception as exc:  # noqa: BLE001
                            result_str = f"Error calling {name}: {exc}"
                            counters["tool_errors"] += 1
                            yield frame(
                                "tool", {"name": name, "status": "error", "preview": result_str}
                            )
                        else:
                            failure = parse_tool_result(result_str)
                            if failure is not None:
                                # The model can recover from a tool error, so it
                                # stays a tool result — but it is never dressed
                                # up as a success.
                                counters["tool_errors"] += 1
                                yield frame(
                                    "tool",
                                    {
                                        "name": name,
                                        "status": "error",
                                        "preview": result_str[:280],
                                        "error": failure.model_dump(mode="json"),
                                    },
                                )
                            else:
                                canvas_dirty = True
                                evidence.ingest(name, arguments, result_str)
                                yield frame(
                                    "tool",
                                    {"name": name, "status": "ok", "preview": result_str[:280]},
                                )
                                source = _source_frame(counters, name, result_str)
                                yield frame(source["event"], source["data"])

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": entry["id"],
                        "name": name,
                        "content": result_str,
                    }
                )

            if canvas_dirty:
                yield frame("canvas_dirty", {"value": True})
                canvas_dirty = False

        counters["rounds_exhausted"] = 1
        final = "".join(spoken)
        note = (
            f"I reached the limit of {MAX_TOOL_ROUNDS} tool rounds for this turn. "
            "Ask me to continue and I will pick up where I left off."
        )
        content = f"{final}\n\n{note}".strip() if final else note
        claims = split_claims(content, evidence)
        _persist_turn(
            memory,
            conversation_id,
            "assistant",
            content,
            assistant_message_id,
            user_message_id,
            claims,
        )
        yield frame("message", _message_payload(content, claims))


async def stream_chat(
    request: ChatRequest,
    service: ConnectorService | None = None,
    memory: StudioMemory | None = None,
    request_id: str | None = None,
    approvals: ApprovalRegistry | None = None,
    local_service: ODIService | None = None,
) -> AsyncIterator[str]:
    """Yield SSE frames: status, conversation, reasoning, delta, tool, approval,
    source, ui, memory, connector, message, error.

    Every turn ends with exactly one terminal event: one ``message`` or one
    ``error``. A failure is never dressed up as a success, and it never leaves
    the stream without an ending.
    """
    rid = request_id or ""
    started = time.monotonic()
    counters = {
        "rounds": 0,
        "tool_calls": 0,
        "tool_errors": 0,
        "rounds_exhausted": 0,
        "sources": 0,
    }
    outcome = "failed"
    error_code: str | None = None
    try:
        async for chunk in _turn_frames(
            request, service, memory, rid, counters, approvals, local_service
        ):
            yield chunk
        outcome = "completed"
        if counters["tool_errors"]:
            outcome = "partial"
        if counters["rounds_exhausted"]:
            outcome = "rounds_exhausted"
    except _TurnFailure as failure:
        yield _error_frame(failure.error, rid)
        outcome = "failed"
        error_code = failure.error.code.value
    except Exception:  # noqa: BLE001
        log.exception("chat turn failed (request_id=%s)", rid)
        yield _error_frame(
            StudioError(
                code=StudioErrorCode.INTERNAL,
                message="The turn failed unexpectedly.",
                suggestion="Try again — your question is still here.",
            ),
            rid,
        )
        outcome = "failed"
    finally:
        log_turn(
            request_id=rid,
            model=request.model,
            rounds=counters["rounds"],
            tool_calls=counters["tool_calls"],
            tool_errors=counters["tool_errors"],
            duration_ms=int((time.monotonic() - started) * 1000),
            outcome=outcome,
            error_code=error_code,
        )


__all__ = [
    "REMEMBER_TOOL",
    "SYSTEM_PROMPT",
    "offline_fallback",
    "stream_chat",
]
