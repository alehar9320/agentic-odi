"""Main CLI entry point."""

import hashlib
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import typer

from agentic_odi_cli import context, paths, update, version
from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.connectors import connectors_app
from agentic_odi_cli.customer_outcomes import customer_outcomes_app, score
from agentic_odi_cli.desired_outcomes import desired_outcomes_app
from agentic_odi_cli.evidence import evidence_app
from agentic_odi_cli.jobs import jobs_app
from agentic_odi_cli.onboard import maybe_run_first_launch
from agentic_odi_cli.profile import app as profile_app
from agentic_odi_cli.profile import setup_wizard
from agentic_odi_cli.settings import settings_app
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

    maybe_run_first_launch(invoked_subcommand=ctx.invoked_subcommand)

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


capabilities_app = typer.Typer(name="capabilities", help="Inspect the assistant's tool surface.")


@capabilities_app.command(name="tools")
def capabilities_tools() -> None:
    """List tool names only."""
    from agentic_odi_core import TOOL_NAMES

    for name in TOOL_NAMES:
        typer.echo(name)


@capabilities_app.callback(invoke_without_command=True)
def capabilities_cmd(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON manifest."),
) -> None:
    """Print what the assistant can do."""
    if ctx.invoked_subcommand is not None:
        return
    from agentic_odi_core import capability_manifest, capability_summary

    if json_output:
        typer.echo(json.dumps(capability_manifest(), indent=2))
    else:
        typer.echo(capability_summary())


app.add_typer(capabilities_app, name="capabilities")
app.add_typer(settings_app, name="settings")
app.add_typer(profile_app, name="profile")
app.command(name="setup", help="Configure product baseline interactively.")(setup_wizard)


@app.command(name="version")
def version_cmd() -> None:
    """Show CLI version."""
    typer.echo(version.build_summary())


@app.command(name="wizard")
def wizard() -> None:
    """Interactive entity creation wizard to guide setup of a Job, Steps, and Outcomes."""
    from agentic_odi_core import compute_opportunity_score

    typer.echo("Welcome to the Agentic ODI Entity Creation Wizard!\n")

    # 1. Job details
    job_name = typer.prompt("Job name", default="My New Job").strip()
    while not job_name:
        typer.echo("Job name cannot be empty.")
        job_name = typer.prompt("Job name", default="My New Job").strip()

    job_description = typer.prompt("Job description", default="").strip()

    # 2. Steps
    steps: list[dict[str, Any]] = []
    typer.echo("\n--- Add Job Steps ---")
    step_count = 1
    while True:
        step_name = typer.prompt("Step name", default=f"Step {step_count}").strip()
        while not step_name:
            typer.echo("Step name cannot be empty.")
            step_name = typer.prompt("Step name", default=f"Step {step_count}").strip()

        while True:
            raw_order = typer.prompt("Step order (int)", default=str(step_count))
            try:
                step_order = int(raw_order)
                break
            except ValueError:
                typer.echo("Please enter a valid integer for step order.")

        steps.append({"name": step_name, "order": step_order})
        step_count += 1

        if not typer.confirm("Add another step?", default=False):
            break

    # 3. Customer Outcomes
    outcomes: list[dict[str, Any]] = []
    typer.echo("\n--- Add Customer Outcomes ---")
    outcome_count = 1
    while True:
        statement = typer.prompt(
            "Outcome statement", default="Minimize time to complete job"
        ).strip()
        while not statement:
            typer.echo("Outcome statement cannot be empty.")
            statement = typer.prompt(
                "Outcome statement", default="Minimize time to complete job"
            ).strip()

        direction = typer.prompt("Direction (minimize/maximize)", default="minimize").strip()
        if direction not in ("minimize", "maximize"):
            direction = "minimize"

        unit_of_measure = typer.prompt("Unit of measure", default="time").strip() or "time"
        object_of_control = (
            typer.prompt("Object of control", default="job execution").strip() or "job execution"
        )

        while True:
            raw_imp = typer.prompt("Outcome importance", default="8.0")
            try:
                importance = float(raw_imp)
                if 1.0 <= importance <= 10.0:
                    break
                typer.echo("Importance score must be between 1.0 and 10.0.")
            except ValueError:
                typer.echo("Please enter a valid number for importance.")

        while True:
            raw_sat = typer.prompt("Outcome satisfaction", default="3.0")
            try:
                satisfaction = float(raw_sat)
                if 1.0 <= satisfaction <= 10.0:
                    break
                typer.echo("Satisfaction score must be between 1.0 and 10.0.")
            except ValueError:
                typer.echo("Please enter a valid number for satisfaction.")

        opp_score = compute_opportunity_score(importance, satisfaction)
        typer.echo(f"Opportunity score: {opp_score:.2f}")

        category = typer.prompt("Business impact category", default="cost_reduction").strip()
        business_statement = (
            typer.prompt("Business value statement", default="Reduces operational overhead").strip()
            or "Reduces operational overhead"
        )

        outcomes.append(
            {
                "statement": statement,
                "direction": direction,
                "unit_of_measure": unit_of_measure,
                "object_of_control": object_of_control,
                "importance": importance,
                "satisfaction": satisfaction,
                "opportunity_score": opp_score,
                "category": category,
                "business_statement": business_statement,
                "step_index": 0 if steps else None,
            }
        )
        outcome_count += 1

        if not typer.confirm("Add another outcome?", default=False):
            break

    # 4. Summary
    typer.echo("\n--- Summary ---")
    typer.echo(f"Job Name: {job_name}")
    if job_description:
        typer.echo(f"Job Description: {job_description}")
    typer.echo("\nSteps:")
    for s in steps:
        typer.echo(f"  - Order {s['order']}: {s['name']}")
    typer.echo("\nCustomer Outcomes:")
    for o in outcomes:
        typer.echo(
            f"  - {o['statement']} (Importance: {o['importance']}, Satisfaction: {o['satisfaction']}, Opportunity Score: {o['opportunity_score']:.2f})"
        )

    # 5. Confirmation & Persistence
    if typer.confirm("Commit this job to the store?", default=True):
        job_args: dict[str, Any] = {"name": job_name}
        if job_description:
            job_args["description"] = job_description
        created_job = run_tool("add_job", job_args)
        job_id = created_job["id"]

        created_customer_outcome_ids: list[str] = []
        for o in outcomes:
            outcome_args: dict[str, Any] = {
                "job_id": job_id,
                "customer_value": {
                    "direction": o["direction"],
                    "unit_of_measure": o["unit_of_measure"],
                    "object_of_control": o["object_of_control"],
                    "statement": o["statement"],
                    "importance": o["importance"],
                    "satisfaction": o["satisfaction"],
                },
                "business_value": {
                    "category": o["category"],
                    "statement": o["business_statement"],
                },
            }
            created_customer_outcome = run_tool("add_customer_outcome", outcome_args)
            created_customer_outcome_ids.append(created_customer_outcome["id"])

        created_step_ids: list[str] = []
        for s in steps:
            created_step = run_tool(
                "add_step", {"job_id": job_id, "name": s["name"], "order": s["order"]}
            )
            created_step_ids.append(created_step["id"])

        for index, outcome in enumerate(outcomes):
            step_index = outcome["step_index"]
            if step_index is not None and step_index < len(created_step_ids):
                run_tool(
                    "update_customer_outcome",
                    {
                        "outcome_id": created_customer_outcome_ids[index],
                        "step_id": created_step_ids[step_index],
                    },
                )

        typer.echo(
            f"\nSuccessfully created Job {job_id} with {len(steps)} step(s) and {len(outcomes)} outcome(s)."
        )
    else:
        typer.echo("\nWizard cancelled. Job was not committed.")


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
