"""Main CLI entry point."""

import hashlib
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import typer

from cli import context, paths, update, version
from cli.connectors import connectors_app
from cli.outcomes import outcomes_app
from cli.version import __version__  # noqa: F401  (re-exported for tests)

app = typer.Typer(
    name="agentic-odi-cli",
    help="Agentic ODI CLI - Tool for managing Jobs-to-be-Done (JTBD) and ODI workflows.",
)
app.add_typer(connectors_app, name="connectors")

app.add_typer(outcomes_app, name="outcomes", help="Manage Customer Outcomes")


def _version_callback(ctx: typer.Context, value: bool) -> None:
    if value:
        if ctx.params.get("verbose"):
            typer.echo(version.verbose_summary())
        else:
            typer.echo(version.build_summary())
        raise typer.Exit()


def _startup_auto_update(no_update: bool) -> None:
    """Best-effort background auto-update; never raises, never blocks."""
    try:
        updated = update.maybe_auto_update(no_update=no_update, now=time.time())
        if updated is not None:
            typer.echo(f"Updated to v{updated} — takes effect next run")
    except Exception:  # noqa: BLE001
        pass


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, help="Show version"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        is_eager=True,
        help="Show verbose version information (with --version)",
    ),
    backend: str | None = typer.Option(None, "--backend", help="Backend: local | mcp"),
    no_update: bool = typer.Option(False, "--no-update", help="Disable the startup update check"),
) -> None:  # noqa: B008
    context.set_backend(backend)
    if not no_update:
        threading.Thread(target=_startup_auto_update, args=(no_update,), daemon=True).start()


def _reexec_current() -> None:
    """Re-exec into the freshly installed binary (POSIX only)."""
    current = paths.current_link()
    binary = current / "odi"
    can_exec = (
        os.name == "posix" and hasattr(os, "execv") and current.is_symlink() and binary.exists()
    )
    if not can_exec:
        typer.echo("Update applied; it will take effect on the next run.")
        return
    argv = sys.argv[1:]
    if "update" in argv:
        argv = argv[: argv.index("update")]
    os.execv(str(binary), [str(binary), *argv])


@app.command(name="version")
def version_cmd() -> None:
    """Show CLI version."""
    typer.echo(version.build_summary())


@app.command(name="update")
def update_cmd(
    check: bool = False,
    force: bool = False,
    version: str | None = None,
    now: bool = False,
) -> None:
    """Check for or apply CLI updates."""
    if check:
        latest = update.latest_release(__version__)
        if latest is None:
            typer.echo(f"Already up to date (v{__version__}).")
        else:
            typer.echo(f"Update available: v{latest} - run 'odi update' to install.")
        return

    if not paths.is_frozen():
        typer.echo("This is a source install; use your package manager to update.")
        return

    target = version.lstrip("v") if version else update.latest_release(__version__)
    if target is None:
        if force:
            target = __version__
        else:
            typer.echo(f"Already up to date (v{__version__}).")
            return

    try:
        with tempfile.TemporaryDirectory(prefix="odi-update-") as tmp:
            archive = update.download(target, Path(tmp))
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            update.perform_update(target, archive, digest, paths.install_root())
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Update failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Updated to v{target}")
    if now:
        _reexec_current()


if __name__ == "__main__":
    app()
