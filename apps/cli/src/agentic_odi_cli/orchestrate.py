"""CLI commands for the OpenHands autopilot orchestrator."""

from __future__ import annotations

import json
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool

orchestrate_app = typer.Typer(
    name="orchestrate",
    help="Queue work for OpenHands Cloud agents and supervise the daemon.",
    no_args_is_help=True,
)


def _service() -> Any:
    from agentic_odi_integrations_openhands import OrchestratorService

    return OrchestratorService()


@orchestrate_app.command(name="start")
def start_cmd(
    once: bool = typer.Option(False, "--once", help="Run a single tick and exit."),
    interval: int | None = typer.Option(
        None, "--interval", help="Seconds between ticks (default: config poll_interval_s)."
    ),
    max_concurrency: int | None = typer.Option(
        None, "--max-concurrency", help="Cap the total number of active runs."
    ),
) -> None:
    """Run the orchestrator daemon in the foreground until SIGINT/SIGTERM."""
    from agentic_odi_integrations_openhands import AlreadyRunning, OrchestratorDaemon

    service = _service()
    if max_concurrency is not None:
        service.settings = service.settings.model_copy(
            update={"max_concurrency": max(1, max_concurrency)}
        )
    daemon = OrchestratorDaemon(service, interval_s=interval, once=once)
    try:
        report = daemon.run()
    except AlreadyRunning as exc:
        typer.secho(f"Error: {exc}", fg="red", err=True)
        raise typer.Exit(code=1) from exc
    if once:
        if report is None:
            typer.echo("No tick ran.")
            return
        typer.echo(
            "Tick complete: "
            f"{report.dispatched} dispatched, "
            f"{report.supervised} supervised, "
            f"{report.terminal} terminal, "
            f"{report.enqueued_schedules} scheduled work queued."
        )
        for error in report.errors:
            typer.secho(f"Warning: {error}", fg="yellow", err=True)


@orchestrate_app.command(name="status")
def status_cmd(
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
) -> None:
    """Show whether the daemon is running and what the queue holds."""
    status = run_tool("get_orchestrator_status", {})
    if as_json:
        typer.echo(json.dumps(status, indent=2))
        return
    state = "running" if status.get("daemon_running") else "not running"
    typer.echo(f"Daemon: {state}")
    if status.get("pid"):
        typer.echo(f"PID: {status['pid']}  Heartbeat: {status.get('heartbeat_at')}")
    typer.echo(
        "Queue: "
        f"{status.get('queued', 0)} queued, "
        f"{status.get('running', 0)} running, "
        f"{status.get('waiting_for_confirmation', 0)} waiting for confirmation"
    )
    typer.echo(
        "Finished: "
        f"{status.get('completed', 0)} completed, "
        f"{status.get('failed', 0)} failed, "
        f"{status.get('blocked', 0)} blocked, "
        f"{status.get('cancelled', 0)} cancelled"
    )
    targets = ", ".join(status.get("targets") or []) or "none configured"
    typer.echo(f"Targets: {targets}")
    typer.echo(f"Config: {status.get('config_path')}")
    typer.echo(f"Store: {status.get('db_path')}")


@orchestrate_app.command(name="add")
def add_cmd(
    title: str = typer.Option(..., "--title", "-t", help="Short title for the work."),
    prompt: str = typer.Option(..., "--prompt", "-p", help="Instructions for the agent."),
    target: str | None = typer.Option(None, "--target", "-a", help="Agent target alias."),
    repo: str | None = typer.Option(None, "--repo", "-r", help="Repository as owner/name."),
    branch: str | None = typer.Option(None, "--branch", "-b", help="Base branch."),
    priority: int = typer.Option(0, "--priority", help="Higher numbers dispatch first."),
    job_id: str | None = typer.Option(None, "--job-id", help="Link to an ODI Job."),
    work_key: str | None = typer.Option(
        None, "--work-key", help="Stable idempotency key; re-adding returns the existing item."
    ),
) -> None:
    """Queue work for an agent. The daemon dispatches it on its next tick."""
    result = run_tool(
        "add_work_item",
        {
            "title": title,
            "prompt": prompt,
            "target": target,
            "repository": repo,
            "branch": branch,
            "priority": priority,
            "job_id": job_id,
            "work_key": work_key,
        },
    )
    work = result.get("work_item", result)
    verb = "Queued" if result.get("created", True) else "Already queued"
    typer.secho(f"{verb} work item {work.get('id')} ({work.get('status')})", fg="green")
    if not result.get("created", True):
        typer.echo(f"Existing work key: {work.get('work_key')}")


@orchestrate_app.command(name="list")
def list_cmd(
    status: str | None = typer.Option(None, "--status", "-s", help="Filter by work status."),
    source: str | None = typer.Option(
        None, "--source", help="Filter by source: manual, github, schedule, studio."
    ),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
) -> None:
    """List work items, newest priority first."""
    items = run_tool("list_work_items", {"status": status, "source": source})
    if as_json:
        typer.echo(json.dumps(items, indent=2))
        return
    if not items:
        typer.echo("No work items.")
        return
    typer.echo(f"{'ID':36}  {'STATUS':24}  {'SOURCE':9}  TITLE")
    for item in items:
        typer.echo(
            f"{str(item.get('id'))[:36]:36}  "
            f"{str(item.get('status'))[:24]:24}  "
            f"{str(item.get('source_kind'))[:9]:9}  "
            f"{str(item.get('title'))[:50]}"
        )


@orchestrate_app.command(name="show")
def show_cmd(
    work_id: str = typer.Argument(..., help="The work item ID."),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
) -> None:
    """Show one work item and its latest run."""
    result = run_tool("get_work_item", {"work_id": work_id})
    if as_json:
        typer.echo(json.dumps(result, indent=2))
        return
    work = result.get("work_item", {})
    typer.echo(f"{work.get('title')} ({work.get('id')})")
    typer.echo(f"Status: {work.get('status')}  Source: {work.get('source_kind')}")
    typer.echo(
        f"Target: {work.get('target_alias')}  Repo: {work.get('repository') or '-'}  "
        f"Branch: {work.get('branch') or '-'}"
    )
    run = result.get("latest_run")
    if not run:
        typer.echo("No run yet.")
        return
    typer.echo(
        f"Run: {run.get('id')} ({run.get('status')})  attempt {run.get('attempt')}  "
        f"cost ${run.get('cost_usd', 0):.2f}"
    )
    if run.get("conversation_url"):
        typer.echo(f"Conversation: {run.get('conversation_url')}")
    for url in run.get("pr_urls") or []:
        typer.echo(f"PR: {url}")
    if run.get("summary"):
        typer.echo(f"Summary: {run.get('summary')}")
    if run.get("error"):
        typer.echo(f"Error: {run.get('error')}")
    if run.get("blocked_reason"):
        typer.echo(f"Blocked: {run.get('blocked_reason')}")


@orchestrate_app.command(name="cancel")
def cancel_cmd(
    work_id: str = typer.Argument(..., help="The work item ID to cancel."),
) -> None:
    """Cancel queued or running work. Running sandboxes are stopped best-effort."""
    result = run_tool("cancel_work_item", {"work_id": work_id})
    typer.secho(f"Cancelled {result.get('id')} ({result.get('status')})", fg="yellow")


@orchestrate_app.command(name="retry")
def retry_cmd(
    work_id: str = typer.Argument(..., help="The finished work item ID to requeue."),
) -> None:
    """Requeue a finished work item, including one that was blocked."""
    result = run_tool("retry_work_item", {"work_id": work_id})
    typer.secho(f"Requeued {result.get('id')} ({result.get('status')})", fg="green")


@orchestrate_app.command(name="agents")
def agents_cmd(
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
) -> None:
    """List configured OpenHands targets."""
    targets = run_tool("list_agent_targets", {})
    if as_json:
        typer.echo(json.dumps(targets, indent=2))
        return
    if not targets:
        typer.echo("No targets configured.")
        return
    for target in targets:
        state = "enabled" if target.get("enabled") else "disabled"
        key = "env key set" if target.get("has_env_key") else "no key"
        typer.echo(
            f"{target.get('alias')}: {target.get('base_url')} ({state}, {key}) "
            f"repo={target.get('repository') or '-'} "
            f"branch={target.get('branch') or '-'} "
            f"concurrency={target.get('max_concurrency')}"
        )


@orchestrate_app.command(name="runs")
def runs_cmd(
    work_id: str | None = typer.Argument(None, help="Only runs for this work item."),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON."),
) -> None:
    """List agent runs, oldest first."""
    runs = run_tool("list_agent_runs", {"work_id": work_id})
    if as_json:
        typer.echo(json.dumps(runs, indent=2))
        return
    if not runs:
        typer.echo("No runs.")
        return
    for run in runs:
        typer.echo(
            f"{run.get('id')}  {str(run.get('status')):24}  "
            f"attempt {run.get('attempt')}  ${run.get('cost_usd', 0):.2f}  "
            f"{run.get('conversation_url') or '-'}"
        )
