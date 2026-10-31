"""Tests for the interactive CLI chat."""

from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace
from typing import Any

from agentic_odi_cli.chat import (
    ChatConfig,
    ChatSession,
    ConnectionState,
    _normalize_tool_calls,
    _to_openai_tools,
    handle_command,
)
from agentic_odi_core import ModelRouter
from agentic_odi_cli.cli import app
from typer.testing import CliRunner

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


def _config() -> ChatConfig:
    return ChatConfig(
        base_url="http://localhost:8001/v1",
        api_key="local",
        model="test-model",
        mcp_url="http://localhost:8000/mcp",
    )


class _FakeSession:
    def __init__(self) -> None:
        self.tool_names = ["add_job", "get_jobs"]
        self.cleared = False
        self.config = _config()
        self.connection_state = ConnectionState(llm_ok=True, mcp_ok=True, mcp_tool_count=2)
        self.router = ModelRouter()

    def clear(self) -> None:
        self.cleared = True

    def update_config(self, new_config: ChatConfig) -> None:
        self.config = new_config
        self.connection_state.llm_ok = True


class _FakeStream:
    def __init__(self, chunks: list[Any]) -> None:
        self._chunks = list(chunks)

    def __aiter__(self) -> _FakeStream:
        return self

    async def __anext__(self) -> Any:
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class _FakeCompletions:
    def __init__(self, streams: list[_FakeStream]) -> None:
        self._streams = list(streams)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> _FakeStream:
        self.calls.append(kwargs)
        return self._streams.pop(0)


class _FakeMCP:
    def __init__(self, tools: list[Any], results: dict[str, str]) -> None:
        self._tools = tools
        self._results = results
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self) -> list[Any]:
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        return SimpleNamespace(content=[SimpleNamespace(text=self._results[name])])


def _chunk(content: str | None = None, tool_calls: list[Any] | None = None) -> Any:
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _make_session(
    streams: list[_FakeStream], tools: list[Any], results: dict[str, str]
) -> tuple[ChatSession, _FakeCompletions, _FakeMCP]:
    completions = _FakeCompletions(streams)
    openai_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    mcp = _FakeMCP(tools, results)
    session = ChatSession(
        _config(), openai_client, mcp, connection_state=ConnectionState(llm_ok=True)
    )
    return session, completions, mcp


def test_chat_help_lists_connection_options() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["chat", "--help"])

    assert result.exit_code == 0
    output = _strip_ansi(result.output)
    assert "--base-url" in output
    assert "--model" in output
    assert "--mcp-url" in output


def test_no_args_without_tty_prints_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--no-update"])

    assert result.exit_code == 0
    assert "Usage" in _strip_ansi(result.output)


def test_config_from_env_uses_variables(monkeypatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_BASE_URL", "http://example.test/v1")
    monkeypatch.setenv("AGENTIC_ODI_API_KEY", "secret")
    monkeypatch.setenv("AGENTIC_ODI_MODEL", "custom-model")
    monkeypatch.setenv("AGENTIC_ODI_MCP_URL", "http://example.test/mcp")

    config = ChatConfig.from_env()

    assert config == ChatConfig(
        base_url="http://example.test/v1",
        api_key="secret",
        model="custom-model",
        mcp_url="http://example.test/mcp",
    )


def test_config_explicit_values_win_over_env(monkeypatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_MODEL", "from-env")

    config = ChatConfig.from_env(model="from-flag")

    assert config.model == "from-flag"


def test_handle_command_routes_and_clears(capsys) -> None:
    session = _FakeSession()

    assert handle_command("hello", session) is None
    assert handle_command("/exit", session) == "exit"
    assert handle_command("/quit", session) == "exit"
    assert handle_command("/help", session) == "handled"
    assert handle_command("/tools", session) == "handled"
    assert handle_command("/clear", session) == "handled"
    assert session.cleared is True
    assert handle_command("/nope", session) == "handled"

    output = capsys.readouterr().out
    assert "add_job" in output
    assert "Unknown command" in output


def test_to_openai_tools_translates_fastmcp_schema() -> None:
    tool = SimpleNamespace(
        name="add_job",
        description=None,
        input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
    )

    assert _to_openai_tools([tool]) == [
        {
            "type": "function",
            "function": {
                "name": "add_job",
                "description": "",
                "parameters": {"type": "object", "properties": {"name": {"type": "string"}}},
            },
        }
    ]


def test_normalize_tool_calls_fills_missing_id_and_arguments() -> None:
    calls = _normalize_tool_calls({0: {"id": "", "name": "get_jobs", "arguments": ""}})

    assert calls == [
        {
            "id": "call_0",
            "type": "function",
            "function": {"name": "get_jobs", "arguments": "{}"},
        }
    ]


def test_session_streams_the_answer_and_executes_tool_calls() -> None:
    tool_start = SimpleNamespace(
        index=0,
        id="call-1",
        function=SimpleNamespace(name="add_job", arguments='{"name": '),
    )
    tool_arguments = SimpleNamespace(
        index=0,
        id=None,
        function=SimpleNamespace(name=None, arguments='"Test"}'),
    )
    first = _FakeStream(
        [
            _chunk(content="Let me add that. ", tool_calls=[tool_start]),
            _chunk(tool_calls=[tool_arguments]),
        ]
    )
    second = _FakeStream([_chunk(content="Added the job.")])
    tools = [
        SimpleNamespace(
            name="add_job",
            description="Add a job",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
        )
    ]
    session, completions, mcp = _make_session(
        [first, second], tools, {"add_job": '{"id": "job-1"}'}
    )

    asyncio.run(session.initialize())
    pieces: list[str] = []
    reply = asyncio.run(session.ask("Add a job named Test", on_delta=pieces.append))

    assert reply == "Added the job."
    assert "".join(pieces) == "Let me add that. Added the job."
    assert mcp.calls == [("add_job", {"name": "Test"})]
    assert completions.calls[0]["stream"] is True
    assert any(
        message.get("role") == "tool" and message.get("content") == '{"id": "job-1"}'
        for message in session.messages
    )


def test_session_rolls_back_failed_turn() -> None:
    class _BoomCompletions:
        async def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("boom")

    openai_client = SimpleNamespace(chat=SimpleNamespace(completions=_BoomCompletions()))
    session = ChatSession(
        _config(), openai_client, _FakeMCP([], {}), connection_state=ConnectionState(llm_ok=True)
    )
    before = list(session.messages)

    try:
        asyncio.run(session.ask("hello"))
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:  # pragma: no cover - the fake always raises
        raise AssertionError("expected RuntimeError")

    assert session.messages == before


def test_session_clear_drops_history() -> None:
    session, _, _ = _make_session([], [], {})
    session.messages.append({"role": "user", "content": "hello"})

    session.clear()

    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "system"


# ---------------------------------------------------------------------------
# Helpers for /status, /model, /mcp tests
# ---------------------------------------------------------------------------


class _FullFakeSession:
    """Fake session satisfying the full ChatSessionLike protocol."""

    def __init__(self, config: ChatConfig, connection_state: ConnectionState) -> None:
        self.config = config
        self.connection_state = connection_state
        self.tool_names: list[str] = ["add_job", "get_jobs"]
        self.cleared = False
        self.router = ModelRouter()

    def clear(self) -> None:
        self.cleared = True

    def update_config(self, new_config: ChatConfig) -> None:
        self.config = new_config
        self.connection_state.llm_ok = True


def _full_session(
    *,
    model: str = "test-model",
    mcp_url: str = "http://localhost:8000/mcp",
    llm_ok: bool = True,
    mcp_ok: bool = True,
    mcp_tool_count: int = 3,
) -> _FullFakeSession:
    config = ChatConfig(
        base_url="http://localhost:8001/v1",
        api_key="local",
        model=model,
        mcp_url=mcp_url,
    )
    conn = ConnectionState(llm_ok=llm_ok, mcp_ok=mcp_ok, mcp_tool_count=mcp_tool_count)
    return _FullFakeSession(config, conn)


# ---------------------------------------------------------------------------
# Tests: /status
# ---------------------------------------------------------------------------


def test_status_shows_model_and_connection_info(capsys) -> None:
    session = _full_session(model="my-model", llm_ok=True, mcp_ok=True, mcp_tool_count=5)

    result = handle_command("/status", session)

    assert result == "handled"
    out = capsys.readouterr().out
    assert "my-model" in out
    assert "connected" in out
    assert "5 tools" in out


def test_status_shows_not_connected_when_offline(capsys) -> None:
    session = _full_session(llm_ok=False, mcp_ok=False)

    handle_command("/status", session)

    out = capsys.readouterr().out
    assert "not connected" in out


# ---------------------------------------------------------------------------
# Tests: /model
# ---------------------------------------------------------------------------


def test_model_command_updates_session_model(capsys) -> None:
    session = _full_session(model="old-model")

    result = handle_command("/model gpt-4o-mini", session)

    assert result == "handled"
    assert session.config.model == "gpt-4o-mini"
    out = capsys.readouterr().out
    assert "gpt-4o-mini" in out


def test_model_command_without_arg_prints_current(capsys) -> None:
    session = _full_session(model="current-model")

    result = handle_command("/model", session)

    assert result == "handled"
    out = capsys.readouterr().out
    assert "current-model" in out
    # Model should be unchanged
    assert session.config.model == "current-model"


def test_model_command_preserves_other_config_fields(capsys) -> None:
    session = _full_session(model="old", mcp_url="http://mcp.test/mcp")

    handle_command("/model new-model", session)

    assert session.config.mcp_url == "http://mcp.test/mcp"
    assert session.config.base_url == "http://localhost:8001/v1"


# ---------------------------------------------------------------------------
# Tests: /mcp
# ---------------------------------------------------------------------------


def test_mcp_command_without_url_prints_current(capsys) -> None:
    session = _full_session(mcp_url="http://localhost:8000/mcp")

    result = handle_command("/mcp", session)

    assert result == "handled"
    out = capsys.readouterr().out
    assert "http://localhost:8000/mcp" in out


def test_mcp_command_calls_reconnect_callback_on_success(capsys) -> None:
    session = _full_session(mcp_url="http://old/mcp", mcp_tool_count=2)
    new_url = "http://new-server/mcp"

    calls: list[str] = []

    def fake_reconnect(url: str) -> bool:
        calls.append(url)
        # Simulate the reconnect updating the session state
        session.connection_state.mcp_tool_count = 7
        return True

    result = handle_command(f"/mcp {new_url}", session, on_mcp_reconnect=fake_reconnect)

    assert result == "handled"
    assert calls == [new_url]
    out = capsys.readouterr().out
    assert new_url in out
    assert "7 tools" in out


def test_mcp_command_reports_failure(capsys) -> None:
    session = _full_session()

    def bad_reconnect(url: str) -> bool:
        return False

    handle_command("/mcp http://bad/mcp", session, on_mcp_reconnect=bad_reconnect)

    out = capsys.readouterr().out
    assert "Failed" in out
    assert "http://bad/mcp" in out


def test_mcp_command_without_callback_prints_unavailable(capsys) -> None:
    session = _full_session()

    handle_command("/mcp http://some/mcp", session)  # no on_mcp_reconnect

    out = capsys.readouterr().out
    assert "not available" in out
