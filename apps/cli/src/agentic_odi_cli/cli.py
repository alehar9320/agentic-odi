"""Main CLI entry point."""

import hashlib
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import typer

from agentic_odi_cli import context, paths, update, version
from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.connectors import connectors_app
from agentic_odi_cli.customer_outcomes import customer_outcomes_app, score
from agentic_odi_cli.desired_outcomes import desired_outcomes_app
from agentic_odi_cli.evidence import evidence_app
from agentic_odi_cli.jobs import jobs_app
from agentic_odi_cli.steps import steps_app
from agentic_odi_cli.version import __version__  # noqa: F401  (re-exported for tests)

app = typer.Typer(
    name="agentic-odi-cli",
    help="Agentic ODI CLI - Tool for managing Jobs-to-be-Done (JTBD) and ODI workflows.",
    no_args_is_help=False,
)
app.add_typer(connectors_app, name="connectors")
app.add_typer(jobs_app, name="jobs", help="Manage Jobs-to-be-Done.")
app.add_typer(steps_app, name="steps", help="Manage Job-map Steps.")
app.add_typer(desired_outcomes_app, name="desired-outcomes", help="Manage desired Outcomes.")
app.add_typer(evidence_app, name="evidence", help="Manage evidence captured from connectors.")
app.add_typer(customer_outcomes_app, name="customer-outcomes", help="Manage Customer Outcomes")
app.add_typer(
    customer_outcomes_app,
    name="outcomes",
    help="Alias for customer-outcomes.",
    hidden=True,
)
app.command(name="score")(score)


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
        return None


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, help="Show version"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        is_eager=True,
        help="Show verbose version information (with --version)",
    ),
    backend: str | None = typer.Option(
        None,
        "--backend",
        help="Backend to use: auto (local, then MCP) | local (SQLite) | mcp (remote server).",
    ),
    db: str | None = typer.Option(
        None, "--db", help="Path to the local SQLite database (local backend)."
    ),
    mcp_url: str | None = typer.Option(None, "--mcp-url", help="MCP server URL (mcp backend)."),
    no_update: bool = typer.Option(False, "--no-update", help="Disable the startup update check"),
) -> None:  # noqa: B008
    context.set_options(backend=backend, db_path=db, mcp_url=mcp_url)
    if not no_update:
        threading.Thread(target=_startup_auto_update, args=(no_update,), daemon=True).start()

    if ctx.invoked_subcommand is None:
        # No subcommand: start the conversational experience when attached to a
        # terminal, otherwise print help so pipes and CI never block on a prompt.
        if sys.stdin.isatty() and sys.stdout.isatty():
            from agentic_odi_cli.chat import ChatConfig, run_chat

            run_chat(ChatConfig.from_env())
        else:
            typer.echo(ctx.get_help())


@app.command(name="chat")
def chat_cmd(
    base_url: str | None = typer.Option(  # noqa: B008
        None,
        "--base-url",
        envvar="AGENTIC_ODI_BASE_URL",
        help="OpenAI-compatible LLM base URL.",
    ),
    model: str | None = typer.Option(  # noqa: B008
        None,
        "--model",
        envvar="AGENTIC_ODI_MODEL",
        help="Model name or alias.",
    ),
    api_key: str | None = typer.Option(  # noqa: B008
        None,
        "--api-key",
        envvar="AGENTIC_ODI_API_KEY",
        help="API key for the LLM endpoint.",
    ),
    mcp_url: str | None = typer.Option(  # noqa: B008
        None,
        "--mcp-url",
        envvar="AGENTIC_ODI_MCP_URL",
        help="Agentic ODI MCP server URL.",
    ),
) -> None:
    """Start an interactive conversation with the ODI assistant (needs the MCP server)."""
    from agentic_odi_cli.chat import ChatConfig, run_chat

    run_chat(
        ChatConfig.from_env(
            base_url=base_url,
            api_key=api_key,
            model=model,
            mcp_url=mcp_url,
        )
    )


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
    os.execv(str(binary), [str(binary), *argv])  # nosec B606 - re-execs own verified binary


@app.command(name="schema")
def schema_cmd() -> None:
    """Print the canonical JSON schema for every ODI entity."""
    typer.echo(json.dumps(run_tool("get_odi_schema", {}), indent=2))


@app.command(name="evaluate")
def evaluate_cmd(
    statement: str = typer.Argument(..., help="Outcome statement to check"),
    job_id: str | None = typer.Option(default=None, help="Job to compare against"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Check whether a statement reads as a well-formed ODI desired outcome."""
    args: dict[str, object] = {"statement": statement}
    if job_id is not None:
        args["job_id"] = job_id
    result = run_tool("evaluate_outcome", args)
    if json_output:
        typer.echo(result if isinstance(result, str) else json.dumps(result))
        return
    parsed = json.loads(result) if isinstance(result, str) else result
    verdict = "passes" if parsed.get("valid") else "needs work"
    typer.echo(f"{verdict}: {statement}")
    for problem in parsed.get("issues", []):
        typer.echo(f"  - {problem}")


@app.command(name="guidelines")
def guidelines_cmd() -> None:
    """Print the ODI framework guidelines."""
    typer.echo(run_tool("get_odi_framework_guidelines", {}))


@app.command(name="capabilities")
def capabilities_cmd() -> None:
    """Print what the assistant can do."""
    typer.echo(run_tool("get_capabilities", {}))


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
