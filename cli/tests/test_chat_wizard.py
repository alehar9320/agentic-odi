"""Tests for the /connect wizard."""

from __future__ import annotations

from types import SimpleNamespace

from cli.chat import ChatConfig, ChatSession, ConnectionState, handle_command
from cli.wizard import run_connect_wizard

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config() -> ChatConfig:
    return ChatConfig(
        base_url="http://localhost:8001/v1",
        api_key="local",
        model="local-tools-model",
        mcp_url="http://localhost:8000/mcp",
    )


class _FakeMCP:
    async def list_tools(self) -> list:
        return []

    async def call_tool(self, name: str, arguments: dict) -> object:
        return SimpleNamespace(content=[])


def _make_session() -> ChatSession:
    return ChatSession(
        _config(),
        SimpleNamespace(),
        _FakeMCP(),
        connection_state=ConnectionState(llm_ok=True),
    )


# ---------------------------------------------------------------------------
# Wizard tests
# ---------------------------------------------------------------------------


def test_wizard_happy_path_openai_preset(monkeypatch) -> None:
    """Full openai preset flow with save=True."""
    prompts = iter(["openai", "https://api.openai.com/v1", "gpt-4o", "http://localhost:8000/mcp"])
    monkeypatch.setattr("typer.prompt", lambda msg, default="": next(prompts))
    monkeypatch.setattr("getpass.getpass", lambda msg="": "sk-test")
    monkeypatch.setattr("typer.confirm", lambda msg, default=True: True)

    saved: list = []
    monkeypatch.setattr("cli.wizard.save_llm_profile", lambda p: saved.append(p))

    result = run_connect_wizard(_config())

    assert result is not None
    assert result.base_url == "https://api.openai.com/v1"
    assert result.model == "gpt-4o"
    assert result.api_key == "sk-test"
    assert len(saved) == 1


def test_wizard_local_preset(monkeypatch) -> None:
    """Local preset flow with save=False — save_llm_profile must not be called."""
    prompts = iter(
        ["local", "http://localhost:8001/v1", "local-tools-model", "http://localhost:8000/mcp"]
    )
    monkeypatch.setattr("typer.prompt", lambda msg, default="": next(prompts))
    monkeypatch.setattr("getpass.getpass", lambda msg="": "local")
    monkeypatch.setattr("typer.confirm", lambda msg, default=True: False)

    saved: list = []
    monkeypatch.setattr("cli.wizard.save_llm_profile", lambda p: saved.append(p))

    result = run_connect_wizard(_config())

    assert result is not None
    assert result.base_url == "http://localhost:8001/v1"
    assert result.model == "local-tools-model"
    assert len(saved) == 0


def test_wizard_ctrl_c_returns_none(monkeypatch) -> None:
    """KeyboardInterrupt at the first prompt returns None."""
    monkeypatch.setattr(
        "typer.prompt", lambda msg, default="": (_ for _ in ()).throw(KeyboardInterrupt())
    )

    result = run_connect_wizard(_config())

    assert result is None


def test_wizard_skipped_save_does_not_write(monkeypatch) -> None:
    """confirm=False means save_llm_profile is never called."""
    prompts = iter(["openai", "https://api.openai.com/v1", "gpt-4o", "http://localhost:8000/mcp"])
    monkeypatch.setattr("typer.prompt", lambda msg, default="": next(prompts))
    monkeypatch.setattr("getpass.getpass", lambda msg="": "sk-test")
    monkeypatch.setattr("typer.confirm", lambda msg, default=True: False)

    saved: list = []
    monkeypatch.setattr("cli.wizard.save_llm_profile", lambda p: saved.append(p))

    result = run_connect_wizard(_config())

    assert result is not None
    assert len(saved) == 0


def test_handle_command_connect_calls_on_connect(capsys) -> None:
    """handle_command('/connect') invokes on_connect and echoes the result."""
    session = _make_session()
    new_config = ChatConfig(
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4o",
        mcp_url="http://localhost:8000/mcp",
    )

    called: list = []

    def _fake_on_connect() -> ChatConfig:
        called.append(True)
        return new_config

    action = handle_command("/connect", session, on_connect=_fake_on_connect)

    assert action == "handled"
    assert len(called) == 1
    output = capsys.readouterr().out
    assert "gpt-4o" in output
    assert "https://api.openai.com/v1" in output


def test_handle_command_connect_without_on_connect(capsys) -> None:
    """/connect without a callback prints a fallback message."""
    session = _make_session()

    action = handle_command("/connect", session)

    assert action == "handled"
    assert "not available" in capsys.readouterr().out


def test_handle_command_connect_on_connect_returns_none(capsys) -> None:
    """/connect when on_connect returns None does not echo connection info."""
    session = _make_session()

    action = handle_command("/connect", session, on_connect=lambda: None)

    assert action == "handled"
    output = capsys.readouterr().out
    # Should not print "Connected:" when wizard returns None
    assert "Connected:" not in output


def test_session_update_config_hot_swaps_and_marks_llm_ok() -> None:
    """ChatSession.update_config replaces config and sets llm_ok=True."""
    session = _make_session()
    session.connection_state.llm_ok = False

    new_config = ChatConfig(
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4o",
        mcp_url="http://localhost:8000/mcp",
    )
    session.update_config(new_config)

    assert session.config is new_config
    assert session.connection_state.llm_ok is True
