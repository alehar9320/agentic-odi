"""Edge tests for the root CLI callback and update re-exec."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from typer.testing import CliRunner

import cli.cli as cli_module
from cli.cli import app


def test_no_args_launches_chat_when_attached_to_a_terminal(monkeypatch) -> None:
    seen: list = []
    monkeypatch.setattr(cli_module.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(cli_module.sys, "stdout", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("cli.chat.run_chat", lambda config: seen.append(config))

    ctx: Any = SimpleNamespace(invoked_subcommand=None)
    cli_module.main(
        ctx,
        version=False,
        verbose=False,
        backend=None,
        db=None,
        mcp_url=None,
        no_update=True,
    )

    assert len(seen) == 1


def test_chat_command_uses_explicit_connection_options(monkeypatch) -> None:
    seen: list = []
    monkeypatch.setattr("cli.chat.run_chat", lambda config: seen.append(config))

    result = CliRunner().invoke(
        app,
        [
            "--no-update",
            "chat",
            "--base-url",
            "http://llm/v1",
            "--api-key",
            "secret",
            "--model",
            "custom",
            "--mcp-url",
            "http://mcp",
        ],
    )

    assert result.exit_code == 0
    config = seen[0]
    assert config.base_url == "http://llm/v1"
    assert config.api_key == "secret"
    assert config.model == "custom"
    assert config.mcp_url == "http://mcp"


def test_reexec_current_replaces_the_process(monkeypatch, tmp_path) -> None:
    version_dir = tmp_path / "versions" / "0.2.0"
    version_dir.mkdir(parents=True)
    binary = version_dir / "odi"
    binary.write_text("#!/bin/sh\n")
    current = tmp_path / "current"
    current.symlink_to(version_dir, target_is_directory=True)
    monkeypatch.setattr(cli_module.paths, "current_link", lambda: current)
    monkeypatch.setattr(cli_module.sys, "argv", ["odi", "update", "--now"])
    calls: list[tuple] = []
    monkeypatch.setattr(cli_module.os, "execv", lambda path, argv: calls.append((path, argv)))

    cli_module._reexec_current()

    assert calls == [(str(current / "odi"), [str(current / "odi")])]


def test_reexec_current_defers_when_not_installed(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(cli_module.paths, "current_link", lambda: tmp_path / "missing")

    cli_module._reexec_current()

    assert "take effect on the next run" in capsys.readouterr().out
