"""Runtime tests for the interactive chat loop and command handlers."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from cli import chat


def _config() -> chat.ChatConfig:
    return chat.ChatConfig(
        base_url="http://localhost:8001/v1",
        api_key="local",
        model="test-model",
        mcp_url="http://localhost:8000/mcp",
    )


def _chunk(content: str | None = None, tool_calls: list[Any] | None = None) -> Any:
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


class _FakeStream:
    def __init__(self, chunks: list[Any]) -> None:
        self._chunks = list(chunks)

    def __aiter__(self) -> _FakeStream:
        return self

    async def __anext__(self) -> Any:
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class _Completions:
    def __init__(
        self, streams: list[_FakeStream] | None = None, error: Exception | None = None
    ) -> None:
        self._streams = list(streams or [])
        self._error = error

    async def create(self, **kwargs: Any) -> _FakeStream:
        if self._error is not None:
            raise self._error
        return self._streams.pop(0)


class _FakeLLM:
    instances: list[_FakeLLM] = []

    def __init__(self, streams, error=None, **kwargs: Any) -> None:
        self.chat = SimpleNamespace(completions=_Completions(streams, error))
        self.closed = False
        _FakeLLM.instances.append(self)

    async def close(self) -> None:
        self.closed = True


class _FakeMCP:
    def __init__(self, tools: list[Any] | None = None, fail_list: bool = False) -> None:
        self._tools = tools or []
        self._fail_list = fail_list
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> _FakeMCP:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def list_tools(self) -> list[Any]:
        if self._fail_list:
            raise RuntimeError("no tools")
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        return SimpleNamespace(content=[SimpleNamespace(text="ok")])


def _tool(name: str = "get_jobs") -> Any:
    return SimpleNamespace(
        name=name,
        description="List jobs",
        input_schema={"type": "object", "properties": {}},
    )


def _inputs(values: list[Any]):
    iterator = iter(values)

    def _input(prompt: str = "") -> str:
        value = next(iterator)
        if isinstance(value, BaseException):
            raise value
        return value

    return _input


def _install(
    monkeypatch,
    *,
    inputs: list[Any],
    streams: list[_FakeStream] | None = None,
    error: Exception | None = None,
    mcp: _FakeMCP | None = None,
) -> None:
    _FakeLLM.instances = []
    monkeypatch.setattr(chat, "Client", lambda url: mcp or _FakeMCP([_tool()]))
    monkeypatch.setattr(chat, "AsyncOpenAI", lambda **kwargs: _FakeLLM(streams, error, **kwargs))
    monkeypatch.setattr("builtins.input", _inputs(inputs))


def test_run_chat_streams_a_reply_and_says_goodbye(monkeypatch, capsys) -> None:
    _install(
        monkeypatch,
        inputs=["/help", "", "hello", "/exit"],
        streams=[_FakeStream([_chunk("Hi "), _chunk("there")])],
    )

    assert asyncio.run(chat._run_chat(_config())) == 0

    output = capsys.readouterr().out
    assert "Hi there" in output
    assert "Commands:" in output
    assert "Goodbye." in output


def test_run_chat_handles_eof(monkeypatch, capsys) -> None:
    _install(monkeypatch, inputs=[EOFError()])

    assert asyncio.run(chat._run_chat(_config())) == 0
    assert "Goodbye." in capsys.readouterr().out


def test_run_chat_continues_after_keyboard_interrupt(monkeypatch, capsys) -> None:
    _install(monkeypatch, inputs=[KeyboardInterrupt(), "/exit"])

    assert asyncio.run(chat._run_chat(_config())) == 0

    output = capsys.readouterr().out
    assert "Use /exit to quit." in output
    assert "Goodbye." in output


def test_run_chat_prints_no_response_for_empty_replies(monkeypatch, capsys) -> None:
    _install(
        monkeypatch,
        inputs=["hello", "/exit"],
        streams=[
            _FakeStream(
                [
                    SimpleNamespace(choices=[]),
                    SimpleNamespace(choices=[SimpleNamespace(delta=None)]),
                    _chunk(None),
                ]
            )
        ],
    )

    assert asyncio.run(chat._run_chat(_config())) == 0

    output = capsys.readouterr().out
    assert "(no response)" in output
    assert "Goodbye." in output


def test_run_chat_reports_turn_errors_and_keeps_running(monkeypatch, capsys) -> None:
    _install(monkeypatch, inputs=["hello", "/exit"], error=RuntimeError("model down"))

    assert asyncio.run(chat._run_chat(_config())) == 0

    captured = capsys.readouterr()
    assert "Error: model down" in captured.err
    assert "Goodbye." in captured.out


def test_run_chat_returns_zero_when_mcp_fails_but_llm_available(monkeypatch, capsys) -> None:
    """MCP failure is a warning, not a fatal error — REPL still starts."""
    _install(monkeypatch, inputs=[EOFError()], mcp=_FakeMCP(fail_list=True))

    assert asyncio.run(chat._run_chat(_config())) == 0

    output = capsys.readouterr().out
    assert "MCP unavailable" in output or "mcp" in output.lower()
    assert _FakeLLM.instances[0].closed is True


def test_run_chat_wraps_keyboard_interrupt(monkeypatch, capsys) -> None:
    def _interrupt(coro):
        coro.close()
        raise KeyboardInterrupt()

    monkeypatch.setattr(chat.asyncio, "run", _interrupt)

    chat.run_chat(_config())

    assert "Goodbye." in capsys.readouterr().out


def test_run_chat_raises_typer_exit_for_failed_runs(monkeypatch) -> None:
    def _failed(coro):
        coro.close()
        return 1

    monkeypatch.setattr(chat.asyncio, "run", _failed)

    with pytest.raises(typer.Exit) as exc_info:
        chat.run_chat(_config())

    assert exc_info.value.exit_code == 1


def test_tool_commands_report_an_empty_tool_list(capsys) -> None:
    session = SimpleNamespace(tool_names=[], clear=lambda: None)

    assert chat.handle_command("/tools", session) == "handled"
    assert "No tools loaded." in capsys.readouterr().out


def test_call_tool_rejects_malformed_arguments() -> None:
    session = chat.ChatSession(_config(), SimpleNamespace(), _FakeMCP())

    invalid = {"function": {"name": "get_jobs", "arguments": "not json"}}
    non_object = {"function": {"name": "get_jobs", "arguments": "[]"}}

    assert asyncio.run(session._call_tool(invalid)).startswith("Error: invalid JSON")
    assert asyncio.run(session._call_tool(non_object)).startswith("Error: arguments")


def test_call_tool_reports_mcp_failures() -> None:
    class _BrokenMCP(_FakeMCP):
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            raise RuntimeError("exploded")

    session = chat.ChatSession(_config(), SimpleNamespace(), _BrokenMCP())

    result = asyncio.run(session._call_tool({"function": {"name": "get_jobs", "arguments": "{}"}}))

    assert result == "Error calling get_jobs: exploded"


def test_call_tool_invokes_the_on_tool_callback() -> None:
    seen: list[tuple[str, dict[str, Any]]] = []
    session = chat.ChatSession(
        _config(),
        SimpleNamespace(),
        _FakeMCP(),
        on_tool=lambda name, arguments: seen.append((name, arguments)),
    )

    asyncio.run(session._call_tool({"function": {"name": "get_jobs", "arguments": '{"a": 1}'}}))

    assert seen == [("get_jobs", {"a": 1})]


def test_print_tool_truncates_long_arguments(capsys) -> None:
    chat._print_tool("add_job", {"name": "x" * 200})

    error = capsys.readouterr().err
    assert "..." in error
    assert len(error.split("add_job", 1)[1].strip()) <= 101


def test_stream_completion_ignores_malformed_chunks() -> None:
    session = chat.ChatSession(_config(), SimpleNamespace(), _FakeMCP())
    session.openai_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=_Completions(
                [
                    _FakeStream(
                        [
                            SimpleNamespace(choices=[]),
                            SimpleNamespace(choices=[SimpleNamespace(delta=None)]),
                            _chunk("ok"),
                        ]
                    )
                ]
            )
        )
    )

    content, tool_calls = asyncio.run(session._stream_completion(None))

    assert content == "ok"
    assert tool_calls == {}


def test_tool_result_text_falls_back_to_the_raw_result() -> None:
    assert chat._tool_result_text("raw") == "raw"
    assert (
        chat._tool_result_text(
            SimpleNamespace(content=[SimpleNamespace(text="a"), SimpleNamespace(text=None)])
        )
        == "a"
    )


def test_repl_starts_with_mcp_failure(monkeypatch, capsys) -> None:
    """REPL starts and returns 0 even when the MCP server is unreachable."""

    class _FailingMCP:
        """Context manager that raises on entry, simulating an unreachable MCP server."""

        async def __aenter__(self) -> _FailingMCP:
            raise OSError("connection refused")

        async def __aexit__(self, *exc: object) -> bool:
            return False

        async def list_tools(self) -> list[object]:
            raise OSError("connection refused")

        async def call_tool(self, name: str, arguments: dict) -> object:
            raise OSError("connection refused")

    _FakeLLM.instances = []
    monkeypatch.setattr(chat, "Client", lambda url: _FailingMCP())
    monkeypatch.setattr(chat, "AsyncOpenAI", lambda **kwargs: _FakeLLM([], None, **kwargs))
    monkeypatch.setattr("builtins.input", _inputs([EOFError()]))

    result = asyncio.run(chat._run_chat(_config()))

    assert result == 0

    output = capsys.readouterr().out
    # Should contain a warning about MCP being unavailable
    assert "mcp" in output.lower() or "unavailable" in output.lower() or "offline" in output.lower()


def test_repl_sends_nudge_when_llm_not_connected() -> None:
    """ChatSession.ask returns a nudge string when llm_ok is False, without calling OpenAI."""
    conn = chat.ConnectionState(llm_ok=False)
    session = chat.ChatSession(
        _config(),
        SimpleNamespace(),  # openai_client — must NOT be called
        _FakeMCP(),
        connection_state=conn,
    )

    result = asyncio.run(session.ask("hello"))

    assert result == "No model connected. Type /connect to set one up."
    # The messages list should be unchanged (nudge doesn't add to history)
    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "system"
