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


def _get_visible_commands(typer_app, prefix="") -> set[str]:
    """Every registered command that is not hidden, as a ``group command`` path.

    A hidden group (``outcomes``, the historical alias of ``customer-outcomes``)
    is not part of the documented surface, so it is skipped along with its
    children. Everything else must appear in ``docs/cli.md``.
    """
    commands: set[str] = set()
    for group in typer_app.registered_groups:
        if getattr(group, "hidden", False):
            continue
        group_name = group.name or ""
        full_prefix = f"{prefix} {group_name}".strip() if prefix else group_name
        commands.add(full_prefix)
        if group.typer_instance:
            commands.update(_get_visible_commands(group.typer_instance, full_prefix))

    for command in typer_app.registered_commands:
        if getattr(command, "hidden", False):
            continue
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


def test_every_visible_command_is_documented() -> None:
    """A new command cannot ship without a line in ``docs/cli.md``.

    This is the enforcement the epic relies on: adding a command to the Typer
    app without documenting it fails here, rather than being noticed in review.
    """
    content = Path("docs/cli.md").read_text(encoding="utf-8")
    missing = sorted(cmd for cmd in _get_visible_commands(app) if cmd not in content)
    assert not missing, "undocumented CLI commands: " + ", ".join(missing)
