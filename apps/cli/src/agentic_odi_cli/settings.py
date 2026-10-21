"""Settings and Feature Flags CLI commands."""

from __future__ import annotations

import json

import typer

from agentic_odi_cli import flags

settings_app = typer.Typer(
    name="settings",
    help="Manage CLI settings and feature flags.",
)

flags_app = typer.Typer(
    name="flags",
    help="Manage feature flags.",
)

settings_app.add_typer(flags_app, name="flags")


@flags_app.command(name="list")
def list_flags(as_json: bool = typer.Option(False, "--json", help="Format output as JSON")) -> None:
    """List all available feature flags and their statuses."""
    store = flags.load_flags()
    items = []
    for key, spec in flags.DEFAULT_FLAGS.items():
        enabled = flags.is_enabled(key)
        persisted = store.flags.get(key)
        items.append(
            {
                "key": key,
                "enabled": enabled,
                "default": spec.default,
                "persisted": persisted,
                "description": spec.description,
            }
        )

    if as_json:
        typer.echo(json.dumps(items, indent=2))
        return

    typer.echo(f"{'FLAG KEY':<25} {'STATE':<10} {'DEFAULT':<10} DESCRIPTION")
    typer.echo("-" * 70)
    for item in items:
        state_str = "ENABLED" if item["enabled"] else "DISABLED"
        default_str = "true" if item["default"] else "false"
        typer.echo(f"{item['key']:<25} {state_str:<10} {default_str:<10} {item['description']}")


@flags_app.command(name="get")
def get_flag(
    key: str = typer.Argument(..., help="Feature flag key"),
    as_json: bool = typer.Option(False, "--json", help="Format output as JSON"),
) -> None:
    """Get the status of a specific feature flag."""
    if key not in flags.DEFAULT_FLAGS:
        typer.echo(f"Error: Unknown feature flag '{key}'", err=True)
        raise typer.Exit(code=1)

    enabled = flags.is_enabled(key)
    spec = flags.DEFAULT_FLAGS[key]
    store = flags.load_flags()

    if as_json:
        typer.echo(
            json.dumps(
                {
                    "key": key,
                    "enabled": enabled,
                    "default": spec.default,
                    "persisted": store.flags.get(key),
                    "description": spec.description,
                },
                indent=2,
            )
        )
        return

    state_str = "ENABLED" if enabled else "DISABLED"
    typer.echo(f"{key}: {state_str} (default: {spec.default})")
    typer.echo(f"Description: {spec.description}")


@flags_app.command(name="set")
def set_flag(
    key: str = typer.Argument(..., help="Feature flag key"),
    value: str = typer.Argument(..., help="Value: true/false, on/off, 1/0"),
) -> None:
    """Enable or disable a feature flag."""
    if key not in flags.DEFAULT_FLAGS:
        typer.echo(f"Error: Unknown feature flag '{key}'", err=True)
        raise typer.Exit(code=1)

    val_lower = value.lower()
    if val_lower in {"true", "1", "on", "yes", "enable", "enabled"}:
        bool_val = True
    elif val_lower in {"false", "0", "off", "no", "disable", "disabled"}:
        bool_val = False
    else:
        typer.echo(f"Error: Invalid boolean value '{value}'", err=True)
        raise typer.Exit(code=1)

    store = flags.load_flags()
    store.set(key, bool_val)
    flags.save_flags(store)

    state_str = "enabled" if bool_val else "disabled"
    typer.echo(f"Feature flag '{key}' set to {state_str}.")


@flags_app.command(name="reset")
def reset_flag(
    key: str | None = typer.Argument(None, help="Feature flag key (or omit to reset all)"),
) -> None:
    """Reset a feature flag (or all flags) to default."""
    store = flags.load_flags()
    if key is not None:
        if key not in flags.DEFAULT_FLAGS:
            typer.echo(f"Error: Unknown feature flag '{key}'", err=True)
            raise typer.Exit(code=1)
        store.reset(key)
        typer.echo(f"Feature flag '{key}' reset to default.")
    else:
        store.reset()
        typer.echo("All feature flags reset to default.")

    flags.save_flags(store)
