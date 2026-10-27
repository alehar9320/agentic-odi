"""Assert that docs/cli.md stays synchronized with registered Typer CLI commands."""

from __future__ import annotations

from pathlib import Path

from agentic_odi_cli.cli import app


def _get_app_commands(typer_app, prefix="") -> set[str]:
    commands: set[str] = set()
    for group in typer_app.registered_groups:
        group_name = group.name or ""
        full_prefix = f"{prefix} {group_name}".strip() if prefix else group_name
        commands.add(full_prefix)
        if group.typer_instance:
            commands.update(_get_app_commands(group.typer_instance, full_prefix))

    for command in typer_app.registered_commands:
        cmd_name = command.name or ""
        full_cmd = f"{prefix} {cmd_name}".strip() if prefix else cmd_name
        if full_cmd:
            commands.add(full_cmd)

    return commands


def test_cli_md_contains_all_registered_commands() -> None:
    doc_path = Path("docs/cli.md")
    assert doc_path.exists(), "docs/cli.md missing"
    content = doc_path.read_text(encoding="utf-8")

    all_commands = _get_app_commands(app)
    expected_top = {
        "capabilities",
        "connectors",
        "jobs",
        "steps",
        "desired-outcomes",
        "evidence",
        "customer-outcomes",
        "settings",
        "profile",
        "setup",
        "chat",
        "schema",
        "score",
        "version",
        "update",
    }

    for cmd in expected_top:
        assert cmd in all_commands, f"Command {cmd} missing from Typer app"
        assert cmd in content, f"Command {cmd} missing from docs/cli.md"
