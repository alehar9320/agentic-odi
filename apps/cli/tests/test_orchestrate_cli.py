from __future__ import annotations

import json

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def _env(tmp_path, monkeypatch) -> None:
    config = tmp_path / "openhands.json"
    config.write_text(
        json.dumps(
            {
                "default_target": "cloud",
                "heartbeat_path": str(tmp_path / "heartbeat.json"),
                "targets": [
                    {
                        "alias": "cloud",
                        "base_url": "https://cloud.test",
                        "repository": "acme/repo",
                        "branch": "odi/work",
                    }
                ],
            }
        )
    )
    monkeypatch.setenv("AGENTIC_ODI_OPENHANDS_CONFIG", str(config))
    monkeypatch.setenv("AGENTIC_ODI_ORCHESTRATOR_DB", str(tmp_path / "orch.db"))
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENHANDS_API_KEY", "test-key")


def test_add_list_show_cancel(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)

    added = runner.invoke(
        app,
        [
            "orchestrate",
            "add",
            "--title",
            "Fix typo",
            "--prompt",
            "Fix the README typo",
        ],
    )
    assert added.exit_code == 0, added.stdout
    assert "Queued work item" in added.stdout

    listed = runner.invoke(app, ["orchestrate", "list", "--json"])
    assert listed.exit_code == 0, listed.stdout
    items = json.loads(listed.stdout)
    assert len(items) == 1
    work_id = items[0]["id"]
    assert items[0]["target_alias"] == "cloud"
    assert items[0]["repository"] == "acme/repo"

    shown = runner.invoke(app, ["orchestrate", "show", work_id, "--json"])
    assert shown.exit_code == 0, shown.stdout
    payload = json.loads(shown.stdout)
    assert payload["work_item"]["title"] == "Fix typo"
    assert payload["latest_run"] is None

    cancelled = runner.invoke(app, ["orchestrate", "cancel", work_id])
    assert cancelled.exit_code == 0, cancelled.stdout
    assert "cancelled" in cancelled.stdout


def test_work_key_is_idempotent(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)
    args = [
        "orchestrate",
        "add",
        "--title",
        "Same work",
        "--prompt",
        "Do it",
        "--work-key",
        "manual:fixed",
    ]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.stdout
    second = runner.invoke(app, args)
    assert second.exit_code == 0, second.stdout
    assert "Already queued" in second.stdout


def test_status_and_agents(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)

    status = runner.invoke(app, ["orchestrate", "status", "--json"])
    assert status.exit_code == 0, status.stdout
    payload = json.loads(status.stdout)
    assert payload["daemon_running"] is False
    assert payload["targets"] == ["cloud"]

    agents = runner.invoke(app, ["orchestrate", "agents", "--json"])
    assert agents.exit_code == 0, agents.stdout
    targets = json.loads(agents.stdout)
    assert targets[0]["alias"] == "cloud"
    assert targets[0]["has_env_key"] is True
    assert targets[0]["api_key"] is None


def test_missing_target_is_a_clean_error(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)
    monkeypatch.delenv("OPENHANDS_API_KEY")
    res = runner.invoke(
        app,
        ["orchestrate", "add", "--title", "T", "--prompt", "P"],
    )
    assert res.exit_code == 1
    assert "no API key" in res.stdout + res.stderr


def test_start_once_finishes_after_one_tick(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)
    res = runner.invoke(app, ["orchestrate", "start", "--once"])
    assert res.exit_code == 0, res.stdout
    assert "Tick complete" in res.stdout


def _seed_terminal_work(
    *,
    title: str = "Fix typo",
    key: str = "manual:seed",
    status: str = "completed",
    error: str | None = None,
    blocked_reason: str | None = None,
) -> str:
    from agentic_odi_integrations_openhands import OrchestratorService
    from agentic_odi_integrations_openhands.models import AgentRun, AgentRunStatus, WorkItemStatus

    service = OrchestratorService()
    work, _ = service.add_work_item(title, "Fix the README typo", work_key=key)
    service.store.update_work_item(work.id, {"status": WorkItemStatus(status)})
    service.store.add_run(
        AgentRun(
            work_item_id=work.id,
            status=AgentRunStatus(status),
            conversation_id="conv-1",
            conversation_url="https://cloud.test/conversations/conv-1",
            cost_usd=1.25,
            tokens=1200,
            summary="Opened a pull request.",
            pr_urls=["https://github.com/acme/repo/pull/7"],
            error=error,
            blocked_reason=blocked_reason,
        )
    )
    service.store.close()
    return work.id


def test_status_human_output(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)
    res = runner.invoke(app, ["orchestrate", "status"])
    assert res.exit_code == 0, res.output
    assert "Daemon: not running" in res.output
    assert "Queue: 0 queued, 0 running, 0 waiting for confirmation" in res.output
    assert "Finished: 0 completed, 0 failed, 0 blocked, 0 cancelled" in res.output
    assert "Targets: cloud" in res.output
    assert "Config:" in res.output
    assert "Store:" in res.output


def test_list_human_output_and_empty_filter(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)
    empty = runner.invoke(app, ["orchestrate", "list"])
    assert empty.exit_code == 0, empty.output
    assert "No work items." in empty.output

    added = runner.invoke(app, ["orchestrate", "add", "--title", "Fix typo", "--prompt", "Do it"])
    assert added.exit_code == 0, added.output
    listed = runner.invoke(app, ["orchestrate", "list"])
    assert listed.exit_code == 0, listed.output
    assert "STATUS" in listed.output
    assert "Fix typo" in listed.output
    no_match = runner.invoke(app, ["orchestrate", "list", "--status", "completed"])
    assert no_match.exit_code == 0, no_match.output
    assert "No work items." in no_match.output


def test_show_human_output_includes_the_real_run(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)
    work_id = _seed_terminal_work()

    shown = runner.invoke(app, ["orchestrate", "show", work_id])
    assert shown.exit_code == 0, shown.output
    assert "Fix typo" in shown.output
    assert "Status: completed" in shown.output
    assert "Run:" in shown.output
    assert "cost $1.25" in shown.output
    assert "Conversation: https://cloud.test/conversations/conv-1" in shown.output
    assert "PR: https://github.com/acme/repo/pull/7" in shown.output
    assert "Summary: Opened a pull request." in shown.output


def test_show_reports_error_and_blocked_reason(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)
    work_id = _seed_terminal_work(
        title="Risky change",
        key="manual:blocked",
        status="blocked",
        error="agent stopped",
        blocked_reason="policy denied the action",
    )

    shown = runner.invoke(app, ["orchestrate", "show", work_id])
    assert shown.exit_code == 0, shown.output
    assert "Error: agent stopped" in shown.output
    assert "Blocked: policy denied the action" in shown.output


def test_retry_human_output(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)
    work_id = _seed_terminal_work(key="manual:retry", status="failed", error="boom")

    retried = runner.invoke(app, ["orchestrate", "retry", work_id])
    assert retried.exit_code == 0, retried.output
    assert "Requeued" in retried.output
    assert "queued" in retried.output


def test_agents_human_output_and_empty_config(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)
    agents = runner.invoke(app, ["orchestrate", "agents"])
    assert agents.exit_code == 0, agents.output
    assert "cloud: https://cloud.test (enabled, env key set)" in agents.output
    assert "repo=acme/repo" in agents.output

    empty_config = tmp_path / "empty.json"
    empty_config.write_text(json.dumps({"targets": []}))
    monkeypatch.setenv("AGENTIC_ODI_OPENHANDS_CONFIG", str(empty_config))
    empty = runner.invoke(app, ["orchestrate", "agents"])
    assert empty.exit_code == 0, empty.output
    assert "No targets configured." in empty.output


def test_runs_human_output_and_empty_result(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)
    empty = runner.invoke(app, ["orchestrate", "runs"])
    assert empty.exit_code == 0, empty.output
    assert "No runs." in empty.output

    work_id = _seed_terminal_work(key="manual:runs")
    runs = runner.invoke(app, ["orchestrate", "runs", work_id])
    assert runs.exit_code == 0, runs.output
    assert "completed" in runs.output
    assert "$1.25" in runs.output
    assert "https://cloud.test/conversations/conv-1" in runs.output


def test_start_once_accepts_overrides_and_surfaces_tick_warnings(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)
    from agentic_odi_integrations_openhands import OrchestratorDaemon
    from agentic_odi_integrations_openhands.service import TickReport

    monkeypatch.setattr(
        OrchestratorDaemon,
        "run",
        lambda self: TickReport(dispatched=2, errors=["github: rate limited"]),
    )
    res = runner.invoke(
        app,
        ["orchestrate", "start", "--once", "--interval", "0", "--max-concurrency", "3"],
    )
    assert res.exit_code == 0, res.output
    assert "2 dispatched" in res.output
    assert "Warning: github: rate limited" in res.output


def test_start_reports_an_already_running_daemon(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)
    from agentic_odi_integrations_openhands import AlreadyRunning, OrchestratorDaemon

    def _fail(self) -> None:
        raise AlreadyRunning("another daemon holds the lock")

    monkeypatch.setattr(OrchestratorDaemon, "run", _fail)
    res = runner.invoke(app, ["orchestrate", "start", "--once"])
    assert res.exit_code == 1
    assert "another daemon holds the lock" in res.output


def test_start_reports_no_tick(tmp_path, monkeypatch) -> None:
    _env(tmp_path, monkeypatch)
    from agentic_odi_integrations_openhands import OrchestratorDaemon

    monkeypatch.setattr(OrchestratorDaemon, "run", lambda self: None)
    res = runner.invoke(app, ["orchestrate", "start", "--once"])
    assert res.exit_code == 0, res.output
    assert "No tick ran." in res.output
