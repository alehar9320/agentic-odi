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
from agentic_odi_core import ODI_ASSISTANT_PROMPT
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
  /help      Show this help
  /status    Show connection status (model, MCP server)
  /connect   Configure LLM provider and MCP server (wizard)
  /model <name>  Switch to a different model
  /mcp <url>     Reconnect to a different MCP server
  /clear     Clear the conversation history
  /tools     List the MCP tools available to the assistant
  /exit      Quit (also /quit)

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
        """Resolve settings in priority order: explicit arg > env var > LLM profile > default."""
        # Lazy import to avoid circular imports between chat and profile.
        from agentic_odi_cli.profile import load_llm_profile  # noqa: PLC0415

        try:
            llm_profile = load_llm_profile()
        except Exception:  # noqa: BLE001
            llm_profile = None

        return cls(
            base_url=(
                base_url
                or os.getenv("AGENTIC_ODI_BASE_URL")
                or (llm_profile.base_url if llm_profile else None)
                or DEFAULT_BASE_URL
            ),
            api_key=(
                api_key
                or os.getenv("AGENTIC_ODI_API_KEY")
                or (llm_profile.api_key if llm_profile else None)
                or DEFAULT_API_KEY
            ),
            model=(
                model
                or os.getenv("AGENTIC_ODI_MODEL")
                or (llm_profile.model if llm_profile else None)
                or DEFAULT_MODEL
            ),
            mcp_url=(
                mcp_url
                or os.getenv("AGENTIC_ODI_MCP_URL")
                or (llm_profile.mcp_url if llm_profile else None)
                or DEFAULT_MCP_URL
            ),
        )


@dataclass
class ConnectionState:
    """Mutable connection status for a chat session."""

    llm_ok: bool = False
    mcp_ok: bool = False
    mcp_tool_count: int = 0
    error_llm: str | None = None
    error_mcp: str | None = None


class ChatSessionLike(Protocol):
    """The session surface the command handler needs."""

    tool_names: list[str]
    config: ChatConfig
    connection_state: ConnectionState

    def clear(self) -> None: ...

    def update_config(self, config: ChatConfig) -> None: ...


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


def handle_command(
    line: str,
    session: ChatSessionLike,
    *,
    on_connect: Callable[[], ChatConfig | None] | None = None,
    on_mcp_reconnect: Callable[[str], bool] | None = None,
) -> Literal["exit", "handled"] | tuple[str, str] | None:
    """Handle a slash command, or return None when the line is a chat message.

    Returns:
        "exit"              — caller should end the session.
        "handled"           — command was handled; continue the REPL.
        ("reconnect_mcp", url) — caller should reconnect MCP then continue.
        None                — not a command; caller should send to the LLM.
    """
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
    if command == "/status":
        state = session.connection_state
        llm_status = "connected" if state.llm_ok else "not connected"
        mcp_status = (
            f"connected ({state.mcp_tool_count} tools)" if state.mcp_ok else "not connected"
        )
        typer.echo(f"model  : {session.config.model}  [{llm_status}]")
        typer.echo(f"url    : {session.config.base_url}")
        typer.echo(f"mcp    : {session.config.mcp_url}  [{mcp_status}]")
        return "handled"
    if command.startswith("/model"):
        parts = line.strip().split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            typer.echo(f"Current model: {session.config.model}")
        else:
            new_model = parts[1].strip()
            new_config = ChatConfig(
                base_url=session.config.base_url,
                api_key=session.config.api_key,
                model=new_model,
                mcp_url=session.config.mcp_url,
            )
            session.update_config(new_config)
            typer.echo(f"Model set to: {new_model}")
        return "handled"
    if command.startswith("/mcp"):
        parts = line.strip().split(None, 1)
        if len(parts) < 2 or not parts[1].strip():
            typer.echo(f"Current MCP URL: {session.config.mcp_url}")
        else:
            new_url = parts[1].strip()
            if on_mcp_reconnect is not None:
                ok = on_mcp_reconnect(new_url)
                if ok:
                    typer.echo(
                        f"MCP reconnected: {new_url} ({session.connection_state.mcp_tool_count} tools)"
                    )
                else:
                    typer.echo(f"Failed to connect to MCP at {new_url}")
            else:
                typer.echo("MCP reconnect not available in this context.")
        return "handled"
    if command == "/connect":
        if on_connect is not None:
            connected_config = on_connect()
            if connected_config is not None:
                typer.echo(f"Connected: {connected_config.model} @ {connected_config.base_url}")
        else:
            typer.echo("Connect wizard not available in this context.")
        return "handled"
    if command.startswith("/"):
        typer.echo(f"Unknown command: {line}. Type /help for commands.")
        return "handled"
    return None


async def _try_connect_mcp(mcp_url: str) -> tuple[Any, list[Any], str | None]:
    """Attempt to connect to the MCP server and list its tools.

    Returns:
        (mcp_client, tools, None) on success.
        (None, [], error_message) on failure.
    """
    try:
        async with Client(mcp_url) as c:
            tools = await c.list_tools()
        # Re-create a fresh context manager for the caller to manage lifetime.
        return Client(mcp_url), tools, None
    except Exception as exc:  # noqa: BLE001
        return None, [], str(exc)


class ChatSession:
    """A streamed tool-calling conversation against an OpenAI-compatible model."""

    def __init__(
        self,
        config: ChatConfig,
        openai_client: Any,
        mcp_client: Any,
        *,
        connection_state: ConnectionState | None = None,
        on_tool: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.config = config
        self.openai_client = openai_client
        self.mcp_client = mcp_client
        self.connection_state = (
            connection_state if connection_state is not None else ConnectionState()
        )
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

    def update_config(self, new_config: ChatConfig) -> None:
        """Hot-swap the session config and mark the LLM connection as live."""
        self.config = new_config
        self.connection_state.llm_ok = True

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
        if not self.connection_state.llm_ok:
            return "No model connected. Type /connect to set one up."

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

    llm: Any | None = None
    conn = ConnectionState()

    try:
        # --- MCP connection (optional) ---
        mcp_client_ctx, tools, mcp_error = await _try_connect_mcp(config.mcp_url)
        if mcp_error is None:
            conn.mcp_ok = True
            conn.mcp_tool_count = len(tools)
        else:
            conn.error_mcp = mcp_error
            typer.secho(
                f"⚠  MCP unavailable ({config.mcp_url}): {mcp_error}",
                fg="yellow",
                err=False,
            )
            typer.secho(
                "   Starting without MCP tools. Use /mcp to reconnect.",
                fg="yellow",
                err=False,
            )

        # --- LLM client (always created; actual reachability found on first use) ---
        llm = AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=60.0,
        )
        conn.llm_ok = True

        # --- Startup banner ---
        mcp_status = f"✓ {conn.mcp_tool_count} tools" if conn.mcp_ok else "✗ offline"
        typer.echo(f"model: {config.model}  ·  mcp: {config.mcp_url} [{mcp_status}]")
        typer.echo("Type /help for commands, /exit to quit.\n")

        # --- Build session ---
        session = ChatSession(
            config,
            llm,
            mcp_client_ctx,  # may be None if MCP is offline
            connection_state=conn,
            on_tool=_print_tool,
        )

        # Populate tools from the probe we already did (avoids a second round-trip).
        if conn.mcp_ok and tools:
            session.tools = _to_openai_tools(tools)
            session.tool_names = [t["function"]["name"] for t in session.tools]

        # --- REPL ---
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

            def _on_connect() -> ChatConfig | None:
                from agentic_odi_cli.wizard import run_connect_wizard  # noqa: PLC0415

                new_config = run_connect_wizard(session.config)
                if new_config is not None:
                    session.update_config(new_config)
                return new_config

            def _on_mcp_reconnect(new_url: str) -> bool:
                """Run MCP reconnect in a separate thread (avoids nested event loops)."""
                import concurrent.futures  # noqa: PLC0415

                async def _reconnect() -> bool:
                    _, new_tools, err = await _try_connect_mcp(new_url)
                    if err is not None:
                        return False
                    new_config = ChatConfig(
                        base_url=session.config.base_url,
                        api_key=session.config.api_key,
                        model=session.config.model,
                        mcp_url=new_url,
                    )
                    session.update_config(new_config)
                    session.mcp_client = Client(new_url)
                    session.tools = _to_openai_tools(new_tools)
                    session.tool_names = [t["function"]["name"] for t in session.tools]
                    session.connection_state.mcp_ok = True
                    session.connection_state.mcp_tool_count = len(new_tools)
                    return True

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(asyncio.run, _reconnect())
                    return future.result()

            action = handle_command(
                line, session, on_connect=_on_connect, on_mcp_reconnect=_on_mcp_reconnect
            )
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
                reply = await session.ask(line, on_delta=on_delta)
            except Exception as exc:  # noqa: BLE001
                typer.echo()
                typer.echo(f"Error: {exc}", err=True)
                continue
            typer.echo()
            if not printed:
                typer.echo(reply if reply else "(no response)")

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
