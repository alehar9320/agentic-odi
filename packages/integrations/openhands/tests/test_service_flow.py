from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from agentic_odi_core import SignalKind
from agentic_odi_integrations_openhands import (
    AgentRun,
    AgentRunStatus,
    AgentTarget,
    OrchestratorService,
    OrchestratorSettings,
    OrchestratorStore,
    WorkItemStatus,
)
from agentic_odi_openhands import AgentServerClient, OpenHandsClient

CLOUD = "https://cloud.test"
AGENT = "https://agent.test"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class FakeCanvas:
    """Just enough OpenHands Cloud and Agent Server to drive the daemon."""

    def __init__(self) -> None:
        self.start_status = "ready"
        self.start_error: int | None = None
        self.execution = "running"
        self.sandbox_status = "RUNNING"
        self.blocked_actions: list[dict[str, Any]] = []
        self.metrics: dict[str, Any] = {"cost": 0.25, "total_tokens": 1200}
        self.events: list[dict[str, Any]] = []
        self.search_results: list[dict[str, Any]] = []
        self.starts: list[dict[str, Any]] = []
        self.policies: list[dict[str, Any]] = []
        self.confirmations: list[dict[str, Any]] = []
        self.paused_sandboxes: list[str] = []
        self.deleted_sandboxes: list[str] = []
        self.deleted_conversations: list[str] = []
        self._counter = 0

    def conversation(self, conversation_id: str = "conv-1") -> dict[str, Any]:
        return {
            "id": conversation_id,
            "sandbox_id": f"sb-{conversation_id}",
            "conversation_url": AGENT,
            "session_api_key": f"session-{conversation_id}",
        }

    def cloud(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path == "/api/v1/app-conversations":
            self.starts.append(json.loads(request.content))
            self._counter += 1
            if self.start_error is not None:
                return httpx.Response(self.start_error, json={"detail": "temporary unavailable"})
            task: dict[str, Any] = {
                "id": f"task-{self._counter}",
                "status": self.start_status,
            }
            if self.start_status == "ready":
                task["app_conversation_id"] = f"conv-{self._counter}"
            elif self.start_status == "error":
                task["error_detail"] = "invalid repository"
            return httpx.Response(200, json=task)
        if path == "/api/v1/app-conversations/start-tasks":
            ids = request.url.params.get_list("ids")
            task = {"id": ids[-1], "status": self.start_status}
            if self.start_status == "ready":
                task["app_conversation_id"] = f"conv-{self._counter}"
            elif self.start_status == "error":
                task["error_detail"] = "invalid repository"
            return httpx.Response(200, json={"items": [task]})
        if path == "/api/v1/app-conversations" and request.method == "GET":
            return httpx.Response(200, json={"items": self.search_results})
        if path.startswith("/api/v1/app-conversations/"):
            conversation_id = path.rsplit("/", 1)[-1]
            if request.method == "DELETE":
                self.deleted_conversations.append(conversation_id)
                return httpx.Response(204)
            return httpx.Response(200, json=self.conversation(conversation_id))
        if path.startswith("/api/v1/sandboxes/"):
            sandbox_id = path.split("/")[4]
            if path.endswith("/pause"):
                self.paused_sandboxes.append(sandbox_id)
                return httpx.Response(200, json={})
            self.deleted_sandboxes.append(sandbox_id)
            return httpx.Response(204)
        return httpx.Response(404, json={"detail": f"unhandled {request.method} {path}"})

    def agent(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/confirmation_policy"):
            self.policies.append(json.loads(request.content))
            return httpx.Response(200, json={})
        if path.endswith("/events/respond_to_confirmation"):
            body = json.loads(request.content)
            body["action_id"] = request.url.params["action_id"]
            self.confirmations.append(body)
            return httpx.Response(200, json={})
        if path.endswith("/events/search"):
            return httpx.Response(200, json={"items": self.events})
        if path.endswith("/pause"):
            return httpx.Response(200, json={})
        if request.method == "DELETE":
            self.deleted_conversations.append(path.rsplit("/", 1)[-1])
            return httpx.Response(204)
        return httpx.Response(
            200,
            json={
                "id": "conv",
                "execution_status": self.execution,
                "sandbox_status": self.sandbox_status,
                "blocked_actions": self.blocked_actions,
                "metrics": self.metrics,
            },
        )


class RecordingSink:
    def __init__(self) -> None:
        self.signals: list[dict[str, Any]] = []

    def record_signal(
        self,
        kind: SignalKind,
        title: str,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        severity: str = "info",
        detail: str | None = None,
        discriminator: str = "",
    ) -> object:
        self.signals.append(
            {
                "kind": kind,
                "title": title,
                "subject_kind": subject_kind,
                "subject_id": subject_id,
                "severity": severity,
                "detail": detail,
                "discriminator": discriminator,
            }
        )
        return object()


def _service(
    tmp_path,
    canvas: FakeCanvas,
    clock: Clock,
    sink: RecordingSink,
    *,
    odi_service: Any | None = None,
    **target_overrides: Any,
) -> OrchestratorService:
    target = AgentTarget(
        alias="cloud",
        base_url=CLOUD,
        api_key="test-key",
        repository="acme/repo",
        branch="main",
        max_attempts=2,
        **target_overrides,
    )
    settings = OrchestratorSettings(
        targets=[target], default_target="cloud", poll_interval_s=1, max_runtime_s=3600
    )
    store = OrchestratorStore(tmp_path / "orch.db")
    return OrchestratorService(
        store=store,
        settings=settings,
        signals=sink,
        odi_service=odi_service,
        cloud_factory=lambda _target: OpenHandsClient(
            CLOUD, api_key="test-key", transport=httpx.MockTransport(canvas.cloud)
        ),
        agent_factory=lambda url, key: AgentServerClient(
            url, key, transport=httpx.MockTransport(canvas.agent)
        ),
        workspace_root=str(tmp_path),
        clock=clock,
    )


def _final_message(text: str = "Opened https://github.com/acme/repo/pull/7") -> dict[str, Any]:
    return {
        "id": "m-1",
        "kind": "MessageEvent",
        "source": "agent",
        "llm_message": {"role": "assistant", "content": [{"text": text}]},
    }


def _pending_action(
    command: str = "pytest -q", risk: str = "LOW", tool: str = "terminal"
) -> dict[str, Any]:
    return {
        "id": "action-1",
        "kind": "ActionEvent",
        "source": "agent",
        "tool_name": tool,
        "tool_call_id": "call-1",
        "action": {"command": command},
        "security_risk": risk,
    }


def test_successful_run_completes_with_pr_and_one_signal(tmp_path) -> None:
    canvas, clock, sink = FakeCanvas(), Clock(), RecordingSink()
    service = _service(tmp_path, canvas, clock, sink)
    work, _ = service.add_work_item("Fix a typo", "Fix the README typo", target_alias="cloud")

    service.tick()
    assert len(canvas.starts) == 1
    assert canvas.starts[0]["selected_repository"] == "acme/repo"
    assert canvas.starts[0]["title"].startswith(f"[odi:{work.id}]")
    assert canvas.starts[0]["observability_metadata"]["odi_work_id"] == work.id
    assert "do not merge" in canvas.starts[0]["system_message_suffix"].lower()
    assert canvas.policies == [
        {"kind": "ConfirmRisky", "threshold": "MEDIUM", "confirm_unknown": True}
    ]
    assert service.get_work_item(work.id).status is WorkItemStatus.RUNNING
    assert sink.signals == []

    canvas.execution = "finished"
    canvas.events = [_final_message()]
    service.tick()

    completed = service.get_work_item(work.id)
    assert completed.status is WorkItemStatus.COMPLETED
    run = service.list_runs(work.id)[-1]
    assert run.status is AgentRunStatus.COMPLETED
    assert run.pr_urls == ["https://github.com/acme/repo/pull/7"]
    assert run.cost_usd == 0.25
    assert len(sink.signals) == 1
    signal = sink.signals[0]
    assert signal["kind"] is SignalKind.AGENT_WORK_COMPLETED
    assert signal["severity"] == "notice"
    assert signal["subject_id"] == run.id
    assert "pull/7" in signal["detail"]
    assert completed.status is WorkItemStatus.COMPLETED

    # A quiet poll afterwards must not emit a second signal.
    service.tick()
    assert len(sink.signals) == 1


def test_confirmation_is_answered_by_the_allowlist(tmp_path) -> None:
    canvas, clock, sink = FakeCanvas(), Clock(), RecordingSink()
    service = _service(tmp_path, canvas, clock, sink)
    work, _ = service.add_work_item("Run tests", "Run the suite", target_alias="cloud")
    service.tick()

    canvas.execution = "waiting_for_confirmation"
    canvas.events = [_pending_action()]
    service.tick()

    assert canvas.confirmations == [
        {"accept": True, "action_id": "action-1"},
    ]
    assert service.get_work_item(work.id).status is WorkItemStatus.WAITING_FOR_CONFIRMATION
    approvals = service.approvals(service.list_runs(work.id)[-1].id)
    assert len(approvals) == 1
    assert approvals[0].rule_id == "command_allowlist"
    assert sink.signals == []

    # The action is recorded, so a repeated poll does not answer it twice.
    service.tick()
    assert len(canvas.confirmations) == 1

    canvas.execution = "running"
    service.tick()
    assert service.get_work_item(work.id).status is WorkItemStatus.RUNNING

    canvas.execution = "finished"
    canvas.events = [_final_message("All tests passed; no PR needed.")]
    service.tick()
    assert service.get_work_item(work.id).status is WorkItemStatus.COMPLETED
    assert len(sink.signals) == 1


def test_dangerous_action_blocks_and_stops_the_sandbox(tmp_path) -> None:
    canvas, clock, sink = FakeCanvas(), Clock(), RecordingSink()
    service = _service(tmp_path, canvas, clock, sink)
    work, _ = service.add_work_item("Clean up", "Clean the repo", target_alias="cloud")
    service.tick()

    canvas.execution = "waiting_for_confirmation"
    canvas.events = [_pending_action("rm -rf /workspace/data")]
    service.tick()

    assert canvas.confirmations == [
        {"accept": False, "action_id": "action-1", "reason": "rm -rf is never allowed"}
    ]
    assert service.get_work_item(work.id).status is WorkItemStatus.BLOCKED
    assert canvas.paused_sandboxes == ["sb-conv-1"]
    assert canvas.deleted_sandboxes == ["sb-conv-1"]
    assert len(sink.signals) == 1
    assert sink.signals[0]["kind"] is SignalKind.AGENT_WORK_BLOCKED
    assert sink.signals[0]["severity"] == "urgent"


def test_blocked_actions_from_a_hook_block_immediately(tmp_path) -> None:
    canvas, clock, sink = FakeCanvas(), Clock(), RecordingSink()
    service = _service(tmp_path, canvas, clock, sink)
    work, _ = service.add_work_item("Inspect", "Inspect", target_alias="cloud")
    service.tick()

    canvas.blocked_actions = [{"tool": "terminal", "reason": "hook"}]
    service.tick()

    assert service.get_work_item(work.id).status is WorkItemStatus.BLOCKED
    assert sink.signals[0]["kind"] is SignalKind.AGENT_WORK_BLOCKED


def test_transient_start_failure_retries_once_then_completes(tmp_path) -> None:
    canvas, clock, sink = FakeCanvas(), Clock(), RecordingSink()
    service = _service(tmp_path, canvas, clock, sink)
    work, _ = service.add_work_item("Flaky", "Do the work", target_alias="cloud")

    canvas.start_error = 503
    service.tick()

    assert len(canvas.starts) == 1
    retried = service.get_work_item(work.id)
    assert retried.status is WorkItemStatus.QUEUED
    assert retried.attempts == 1
    assert retried.next_attempt_at is not None
    assert sink.signals == []

    # Backoff has not elapsed yet.
    service.tick()
    assert len(canvas.starts) == 1

    clock.advance(61)
    canvas.start_error = None
    canvas.execution = "finished"
    canvas.events = [_final_message("Done with no PR.")]
    service.tick()
    # The dispatch and the first supervision happen in the same tick.
    service.tick()

    assert len(canvas.starts) == 2
    assert service.get_work_item(work.id).status is WorkItemStatus.COMPLETED
    runs = service.list_runs(work.id)
    assert [run.status for run in runs] == [AgentRunStatus.FAILED, AgentRunStatus.COMPLETED]
    # Only the terminal success emits a signal.
    assert [signal["kind"] for signal in sink.signals] == [SignalKind.AGENT_WORK_COMPLETED]


def test_non_retryable_start_error_fails_immediately(tmp_path) -> None:
    canvas, clock, sink = FakeCanvas(), Clock(), RecordingSink()
    service = _service(tmp_path, canvas, clock, sink)
    work, _ = service.add_work_item("Bad repo", "Do the work", target_alias="cloud")

    canvas.start_status = "error"
    service.tick()

    failed = service.get_work_item(work.id)
    assert failed.status is WorkItemStatus.FAILED
    assert len(canvas.starts) == 1
    assert [s["kind"] for s in sink.signals] == [SignalKind.AGENT_WORK_FAILED]


def test_recovery_never_starts_a_duplicate(tmp_path) -> None:
    canvas, clock, sink = FakeCanvas(), Clock(), RecordingSink()
    service = _service(tmp_path, canvas, clock, sink)
    work, _ = service.add_work_item("Crashy", "Do the work", target_alias="cloud")
    run = service.store.add_run(AgentRun(work_item_id=work.id, status=AgentRunStatus.PENDING))
    service.store.update_work_item(work.id, {"status": WorkItemStatus.DISPATCHING, "attempts": 1})

    canvas.search_results = []
    service.recover()

    assert canvas.starts == []
    assert service.get_work_item(work.id).status is WorkItemStatus.BLOCKED
    assert "refusing to dispatch a duplicate" in (service.get_run(run.id).blocked_reason or "")
    assert [s["kind"] for s in sink.signals] == [SignalKind.AGENT_WORK_BLOCKED]


def test_recovery_adopts_an_exact_single_match(tmp_path) -> None:
    canvas, clock, sink = FakeCanvas(), Clock(), RecordingSink()
    service = _service(tmp_path, canvas, clock, sink)
    work, _ = service.add_work_item("Crashy", "Do the work", target_alias="cloud")
    run = service.store.add_run(AgentRun(work_item_id=work.id, status=AgentRunStatus.PENDING))
    service.store.update_work_item(work.id, {"status": WorkItemStatus.DISPATCHING, "attempts": 1})

    canvas.search_results = [canvas.conversation("conv-existing")]
    service.recover()

    assert canvas.starts == []
    adopted = service.get_run(run.id)
    assert adopted.status is AgentRunStatus.RUNNING
    assert adopted.conversation_id == "conv-existing"
    assert adopted.policy_verified is True
    assert service.get_work_item(work.id).status is WorkItemStatus.RUNNING


def test_cancelled_work_emits_no_signal(tmp_path) -> None:
    canvas, clock, sink = FakeCanvas(), Clock(), RecordingSink()
    service = _service(tmp_path, canvas, clock, sink)
    work, _ = service.add_work_item("Cancel me", "Do the work", target_alias="cloud")
    service.tick()
    service.cancel_work_item(work.id)
    service.tick()

    assert service.get_work_item(work.id).status is WorkItemStatus.CANCELLED
    assert sink.signals == []


def _odi_store() -> Any:
    from agentic_odi_core import InMemoryRepository, ODIService

    return ODIService(InMemoryRepository())


def test_due_one_shot_schedule_is_queued_then_completed(tmp_path) -> None:
    canvas, clock, sink = FakeCanvas(), Clock(), RecordingSink()
    odi = _odi_store()
    service = _service(tmp_path, canvas, clock, sink, odi_service=odi)
    schedule = odi.schedule_work(
        name="Nightly audit",
        schedule_expression="+1h",
        payload={"title": "Nightly audit", "prompt": "Audit the backlog", "target": "cloud"},
    )

    service.tick()
    assert service.list_work_items() == []
    assert odi.get_scheduled_work(schedule.id).status.value == "scheduled"

    odi.trigger_scheduled_work(schedule.id)
    # The core service stamps the request with the real clock; align ours so
    # the queued occurrence is due.
    clock.now = datetime.now(timezone.utc)
    report = service.tick()

    assert report.enqueued_schedules == 1
    items = service.list_work_items()
    assert len(items) == 1
    assert items[0].source_kind.value == "schedule"
    assert items[0].source_ref == schedule.id
    assert items[0].work_key.startswith(f"schedule:{schedule.id}:")
    queued = odi.get_scheduled_work(schedule.id)
    assert queued.status.value == "running"
    assert queued.next_run_at is None
    assert "queued for the orchestrator" in (queued.result_summary or "").lower()

    canvas.execution = "finished"
    canvas.events = [_final_message("Audit complete; no PR.")]
    service.tick()
    service.tick()

    finished = odi.get_scheduled_work(schedule.id)
    assert finished.status.value == "completed"
    assert "Audit complete" in (finished.result_summary or "")
    assert [s["kind"] for s in sink.signals] == [SignalKind.AGENT_WORK_COMPLETED]


def test_recurring_schedule_advances_and_does_not_duplicate(tmp_path) -> None:
    canvas, clock, sink = FakeCanvas(), Clock(), RecordingSink()
    odi = _odi_store()
    service = _service(tmp_path, canvas, clock, sink, odi_service=odi)
    schedule = odi.schedule_work(
        name="Daily sweep",
        schedule_expression="0 9 * * *",
        payload={"prompt": "Sweep", "target": "cloud"},
    )
    past = (clock.now - timedelta(minutes=1)).isoformat()
    odi.repo.update_scheduled_work(schedule.id, {"next_run_at": past})

    report = service.tick()
    assert report.enqueued_schedules == 1
    updated = odi.get_scheduled_work(schedule.id)
    assert updated.status.value == "scheduled"
    assert updated.next_run_at is not None
    assert datetime.fromisoformat(updated.next_run_at) > clock.now
    keys = {item.work_key for item in service.list_work_items()}
    assert keys == {f"schedule:{schedule.id}:{past}"}

    service.tick()
    assert len(service.list_work_items()) == 1


def _record_spend(service, clock, amount: float) -> None:
    spent, _ = service.add_work_item("Earlier spend", "Earlier spend", target_alias="cloud")
    service.store.update_work_item(
        spent.id,
        {"status": WorkItemStatus.COMPLETED},
    )
    service.store.add_run(
        AgentRun(
            work_item_id=spent.id,
            status=AgentRunStatus.COMPLETED,
            cost_usd=amount,
            started_at=clock.now,
            finished_at=clock.now,
        )
    )


def test_daily_cost_limit_stops_new_dispatch(tmp_path) -> None:
    canvas, clock, sink = FakeCanvas(), Clock(), RecordingSink()
    service = _service(tmp_path, canvas, clock, sink)
    service.settings = service.settings.model_copy(update={"daily_cost_limit_usd": 5.0})
    _record_spend(service, clock, 6.0)
    work, _ = service.add_work_item("New work", "Do it", target_alias="cloud")

    report = service.tick()

    assert canvas.starts == []
    assert service.get_work_item(work.id).status is WorkItemStatus.QUEUED
    assert any("daily cost limit" in error for error in report.errors)


def test_target_daily_cost_limit_stops_new_dispatch(tmp_path) -> None:
    canvas, clock, sink = FakeCanvas(), Clock(), RecordingSink()
    service = _service(tmp_path, canvas, clock, sink, daily_cost_limit_usd=2.5)
    _record_spend(service, clock, 3.0)
    work, _ = service.add_work_item("New work", "Do it", target_alias="cloud")

    report = service.tick()

    assert canvas.starts == []
    assert service.get_work_item(work.id).status is WorkItemStatus.QUEUED
    assert any(error.startswith("cloud: daily cost limit") for error in report.errors)
