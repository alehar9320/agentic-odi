"""Interactive conversational mode for the Agentic ODI CLI.

The chat is a small terminal REPL around an OpenAI-compatible model and the
Agentic ODI MCP server. It streams assistant text, executes MCP tool calls,
and keeps the conversation history in memory for the duration of the session.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import typer
from core import ODI_ASSISTANT_PROMPT
from fastmcp import Client
from openai import AsyncOpenAI

DEFAULT_BASE_URL = "http://localhost:8001/v1"
DEFAULT_API_KEY = "local"
DEFAULT_MODEL = "local-tools-model"
DEFAULT_MCP_URL = "http://localhost:8000/mcp"

SYSTEM_PROMPT = (
    ODI_ASSISTANT_PROMPT
    + """

You are running in a terminal chat. Use the available MCP tools to create and
query Jobs, Steps, Desired Outcomes, and Customer Outcomes instead of inventing
records or IDs. Follow the ODI outcome statement format and flag opportunity
scores above 10 as underserved. Keep answers concise and readable as plain text.
"""
)

HELP_TEXT = """Commands:
  /help   Show this help
  /clear  Clear the conversation history
  /tools  List the MCP tools available to the assistant
  /exit   Quit (also /quit)

Anything else is sent to the ODI assistant."""


@dataclass(frozen=True)
class ChatConfig:
    """Connection settings for an interactive chat session."""

    base_url: str
    api_key: str
    model: str
    mcp_url: str

    @classmethod
    def from_env(
        cls,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        mcp_url: str | None = None,
    ) -> ChatConfig:
        """Resolve explicit values first, then environment variables, then defaults."""
        return cls(
            base_url=base_url or os.getenv("AGENTIC_ODI_BASE_URL") or DEFAULT_BASE_URL,
            api_key=api_key or os.getenv("AGENTIC_ODI_API_KEY") or DEFAULT_API_KEY,
            model=model or os.getenv("AGENTIC_ODI_MODEL") or DEFAULT_MODEL,
            mcp_url=mcp_url or os.getenv("AGENTIC_ODI_MCP_URL") or DEFAULT_MCP_URL,
        )


class ChatSessionLike(Protocol):
    """The session surface the command handler needs."""

    tool_names: list[str]

    def clear(self) -> None: ...


def _to_openai_tools(tools: list[Any]) -> list[dict[str, Any]]:
    """Translate FastMCP tool definitions into OpenAI function schemas."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema or {"type": "object", "properties": {}},
            },
        }
        for tool in tools
    ]


def _normalize_tool_calls(entries: dict[int, dict[str, str]]) -> list[dict[str, Any]]:
    """Turn the per-index streaming tool-call buffers into OpenAI tool calls."""
    return [
        {
            "id": entry["id"] or f"call_{index}",
            "type": "function",
            "function": {
                "name": entry["name"],
                "arguments": entry["arguments"] or "{}",
            },
        }
        for index, entry in entries.items()
    ]


def _tool_result_text(result: Any) -> str:
    """Extract readable text from an MCP tool result."""
    content = getattr(result, "content", None) or []
    parts = [getattr(item, "text", None) for item in content]
    text = "\n".join(part for part in parts if part)
    return text or str(result)


def handle_command(line: str, session: ChatSessionLike) -> Literal["exit", "handled"] | None:
    """Handle a slash command, or return None when the line is a chat message."""
    command = line.strip().lower()
    if command in {"/exit", "/quit"}:
        return "exit"
    if command == "/help":
        typer.echo(HELP_TEXT)
        return "handled"
    if command == "/clear":
        session.clear()
        typer.echo("Conversation cleared.")
        return "handled"
    if command == "/tools":
        if session.tool_names:
            typer.echo("\n".join(session.tool_names))
        else:
            typer.echo("No tools loaded.")
        return "handled"
    if command.startswith("/"):
        typer.echo(f"Unknown command: {line}. Type /help for commands.")
        return "handled"
    return None


class ChatSession:
    """A streamed tool-calling conversation against an OpenAI-compatible model."""

    def __init__(
        self,
        config: ChatConfig,
        openai_client: Any,
        mcp_client: Any,
        *,
        on_tool: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.config = config
        self.openai_client = openai_client
        self.mcp_client = mcp_client
        self.on_tool = on_tool
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.tools: list[dict[str, Any]] = []
        self.tool_names: list[str] = []

    async def initialize(self) -> None:
        """Discover the MCP tools once and expose them to the model."""
        tools = await self.mcp_client.list_tools()
        self.tools = _to_openai_tools(tools)
        self.tool_names = [tool["function"]["name"] for tool in self.tools]

    def clear(self) -> None:
        """Drop the conversation history but keep the system prompt and tools."""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    async def _stream_completion(
        self, on_delta: Callable[[str], None] | None
    ) -> tuple[str, dict[int, dict[str, str]]]:
        stream: Any = await self.openai_client.chat.completions.create(
            model=self.config.model,
            messages=self.messages,
            tools=self.tools or None,
            tool_choice="auto" if self.tools else None,
            stream=True,
        )

        content_parts: list[str] = []
        tool_calls: dict[int, dict[str, str]] = {}

        async for chunk in stream:
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = choices[0].delta
            if delta is None:
                continue
            content = getattr(delta, "content", None)
            if content:
                content_parts.append(content)
                if on_delta is not None:
                    on_delta(content)
            for tool_call in getattr(delta, "tool_calls", None) or []:
                entry = tool_calls.setdefault(
                    tool_call.index, {"id": "", "name": "", "arguments": ""}
                )
                if tool_call.id:
                    entry["id"] = tool_call.id
                function = getattr(tool_call, "function", None)
                if function is not None:
                    if function.name:
                        entry["name"] = function.name
                    if function.arguments:
                        entry["arguments"] += function.arguments

        return "".join(content_parts), tool_calls

    async def _call_tool(self, call: dict[str, Any]) -> str:
        name = call["function"]["name"]
        raw_arguments = call["function"].get("arguments") or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return f"Error: invalid JSON arguments for {name}: {raw_arguments}"
        if not isinstance(arguments, dict):
            return f"Error: arguments for {name} must be a JSON object"
        if self.on_tool is not None:
            self.on_tool(name, arguments)
        try:
            result = await self.mcp_client.call_tool(name, arguments)
        except Exception as exc:  # noqa: BLE001
            return f"Error calling {name}: {exc}"
        return _tool_result_text(result)

    async def ask(self, text: str, on_delta: Callable[[str], None] | None = None) -> str:
        """Send a message, execute any tool calls, and return the final text."""
        checkpoint = len(self.messages)
        self.messages.append({"role": "user", "content": text})
        try:
            while True:
                content, tool_calls = await self._stream_completion(on_delta)
                if not tool_calls:
                    self.messages.append({"role": "assistant", "content": content})
                    return content

                normalized = _normalize_tool_calls(tool_calls)
                self.messages.append(
                    {"role": "assistant", "content": content or None, "tool_calls": normalized}
                )
                for call in normalized:
                    result = await self._call_tool(call)
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "name": call["function"]["name"],
                            "content": result,
                        }
                    )
        except Exception:
            del self.messages[checkpoint:]
            raise


def _print_tool(name: str, arguments: dict[str, Any]) -> None:
    rendered = json.dumps(arguments, ensure_ascii=False)
    if len(rendered) > 100:
        rendered = rendered[:97] + "..."
    typer.secho(f"  → {name} {rendered}", fg="bright_black", err=True)


async def _run_chat(config: ChatConfig) -> int:
    typer.echo("Agentic ODI · interactive")
    typer.echo(f"model: {config.model}  ·  mcp: {config.mcp_url}")
    typer.echo("Type /help for commands, /exit to quit.\n")

    llm: Any | None = None
    try:
        async with Client(config.mcp_url) as mcp_client:
            llm = AsyncOpenAI(
                base_url=config.base_url,
                api_key=config.api_key,
                timeout=60.0,
            )
            session = ChatSession(config, llm, mcp_client, on_tool=_print_tool)
            await session.initialize()

            while True:
                try:
                    line = input("you › ").strip()
                except EOFError:
                    typer.echo()
                    break
                except KeyboardInterrupt:
                    typer.echo("\nUse /exit to quit.")
                    continue

                if not line:
                    continue

                action = handle_command(line, session)
                if action == "exit":
                    break
                if action == "handled":
                    continue

                typer.secho("odi › ", fg="green", bold=True, nl=False)
                printed = False

                def on_delta(piece: str) -> None:
                    nonlocal printed
                    printed = True
                    typer.echo(piece, nl=False)

                try:
                    await session.ask(line, on_delta=on_delta)
                except Exception as exc:  # noqa: BLE001
                    typer.echo()
                    typer.echo(f"Error: {exc}", err=True)
                    continue
                typer.echo()
                if not printed:
                    typer.echo("(no response)")
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Error: could not start chat: {exc}", err=True)
        typer.echo(
            f"MCP server: {config.mcp_url} (`python -m mcp_server`)\n"
            f"LLM endpoint: {config.base_url}",
            err=True,
        )
        return 1
    finally:
        if llm is not None:
            await llm.close()

    typer.echo("Goodbye.")
    return 0


def run_chat(config: ChatConfig) -> None:
    """Run the interactive chat until the user exits."""
    try:
        exit_code = asyncio.run(_run_chat(config))
    except KeyboardInterrupt:
        typer.echo("\nGoodbye.")
        return
    if exit_code:
        raise typer.Exit(code=exit_code)
