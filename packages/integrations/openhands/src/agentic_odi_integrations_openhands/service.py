"""Queue, dispatch, supervise, and finish OpenHands work.

The service is synchronous on purpose: the daemon tick calls it, tests call it
directly, and the CLI/MCP surfaces only add, read, cancel, or retry. Every
state change is persisted before the next network call so a crash leaves a
readable, resumable record rather than an invisible agent.
"""

from __future__ import annotations

import fnmatch
import json
import os
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from agentic_odi_core import ScheduledWorkStatus
from agentic_odi_core.schedule_expr import next_occurrence
from agentic_odi_openhands.client import AgentServerClient, OpenHandsClient
from agentic_odi_openhands.events import final_message, pending_actions, pr_urls
from agentic_odi_openhands.models import (
    ActionEvent,
    ConversationInfo,
    Event,
    ExecutionStatus,
    SandboxStatus,
    StartTask,
)

from agentic_odi_integrations_openhands import config
from agentic_odi_integrations_openhands.adapters.odi import (
    OdiScheduleAdapter,
    OdiSignalAdapter,
)
from agentic_odi_integrations_openhands.issue_tracker.github import GitHubIssueTracker
from agentic_odi_integrations_openhands.models import (
    AgentRun,
    AgentRunStatus,
    AgentTarget,
    ApprovalRecord,
    Decision,
    OrchestratorSettings,
    OrchestratorStatus,
    SourceKind,
    WorkItem,
    WorkItemStatus,
    serialize,
    utcnow,
)
from agentic_odi_integrations_openhands.policy import (
    ActionRequest,
    ApprovalPolicy,
    PolicyDecision,
    args_digest,
)
from agentic_odi_integrations_openhands.ports import IssueTrackerPort, SchedulePort
from agentic_odi_integrations_openhands.signals import SignalSink, terminal_signal
from agentic_odi_integrations_openhands.store import OrchestratorStore

if TYPE_CHECKING:
    from agentic_odi_integrations_openhands.github_source import GitHubSource

DEFAULT_BOUNDARY = (
    "Open a pull request when the work is done. Do not merge it. "
    "Do not push to the default branch; use a feature branch. "
    "Run the relevant tests before opening the PR. "
    "End with a short summary and the PR URL, or say plainly that no PR was opened."
)

_TERMINAL_WORK_FOR_RUN = {
    AgentRunStatus.COMPLETED: WorkItemStatus.COMPLETED,
    AgentRunStatus.FAILED: WorkItemStatus.FAILED,
    AgentRunStatus.BLOCKED: WorkItemStatus.BLOCKED,
    AgentRunStatus.CANCELLED: WorkItemStatus.CANCELLED,
}


class OrchestratorError(Exception):
    """Base class for user-facing orchestration failures."""


class WorkItemNotFound(OrchestratorError):
    pass


class TargetNotConfigured(OrchestratorError):
    pass


class InvalidTransition(OrchestratorError):
    pass


class CloudClient(Protocol):
    def start_conversation(
        self,
        initial_message: str,
        *,
        repository: str | None = None,
        branch: str | None = None,
        llm_model: str | None = None,
        agent_profile_id: str | None = None,
        agent_type: str | None = None,
        plugins: list[dict[str, Any]] | None = None,
        title: str | None = None,
        system_message_suffix: str | None = None,
        observability_metadata: dict[str, str] | None = None,
        observability_tags: list[str] | None = None,
    ) -> StartTask: ...
    def get_start_task(self, task_id: str) -> StartTask | None: ...
    def get_conversation(self, conversation_id: str) -> ConversationInfo: ...
    def search_conversations(self, title_contains: str) -> list[ConversationInfo]: ...
    def resume_sandbox(self, sandbox_id: str) -> None: ...
    def pause_sandbox(self, sandbox_id: str) -> None: ...
    def delete_sandbox(self, sandbox_id: str) -> None: ...
    def delete_conversation(self, conversation_id: str) -> None: ...


class ConversationAgent(Protocol):
    def get_conversation(self, conversation_id: str) -> ConversationInfo: ...
    def search_events(
        self, conversation_id: str, *, page_id: str | None = None, limit: int = 100
    ) -> Any: ...
    def set_confirmation_policy(self, conversation_id: str, policy: Any) -> None: ...
    def respond_to_confirmation(
        self, conversation_id: str, action_id: str, accept: bool, reason: str | None = None
    ) -> None: ...
    def pause_conversation(self, conversation_id: str) -> None: ...
    def delete_conversation(self, conversation_id: str) -> None: ...


@dataclass
class TickReport:
    enqueued_schedules: int = 0
    github_created: int = 0
    issues_created: int = 0
    automation_adopted: int = 0
    dispatched: int = 0
    supervised: int = 0
    terminal: int = 0
    errors: list[str] = field(default_factory=list)


def _default_cloud(target: AgentTarget) -> CloudClient:
    return OpenHandsClient(
        target.base_url,
        api_key=target.resolved_api_key,
        auth_header=target.auth_header,
    )


def _default_agent(conversation_url: str, session_api_key: str | None) -> ConversationAgent:
    return AgentServerClient(conversation_url, session_api_key)


def _transient(error: Exception) -> bool:
    from agentic_odi_openhands.errors import RateLimitError, TransientError

    return isinstance(error, (RateLimitError, TransientError))


def _transient_start_error(message: str) -> bool:
    lowered = message.lower()
    return any(
        needle in lowered
        for needle in (
            "rate limit",
            "timeout",
            "timed out",
            "temporar",
            "unavailable",
            "502",
            "503",
            "504",
        )
    )


def _cost_and_tokens(info: ConversationInfo) -> tuple[float, int]:
    metrics = info.metrics or {}
    cost = 0.0
    for key in ("accumulated_cost", "cost", "total_cost_usd", "total_cost"):
        value = metrics.get(key)
        if isinstance(value, (int, float)):
            cost = float(value)
            break
    tokens = 0
    for key in ("total_tokens", "accumulated_tokens", "tokens"):
        value = metrics.get(key)
        if isinstance(value, int):
            tokens = value
            break
    if not tokens:
        usage = metrics.get("token_usage")
        if isinstance(usage, dict):
            tokens = sum(
                int(part.get("total_tokens", 0))
                for part in usage.values()
                if isinstance(part, dict) and isinstance(part.get("total_tokens"), int)
            )
    return cost, tokens


class OrchestratorService:
    def __init__(
        self,
        store: OrchestratorStore | None = None,
        settings: OrchestratorSettings | None = None,
        *,
        signals: SignalSink | None = None,
        schedule: SchedulePort | None = None,
        issue_tracker: IssueTrackerPort | None = None,
        cloud_factory: Callable[[AgentTarget], CloudClient] | None = None,
        agent_factory: Callable[[str, str | None], ConversationAgent] | None = None,
        workspace_root: str | None = None,
        owner: str | None = None,
        rejection_limit: int | None = None,
        clock: Callable[[], datetime] | None = None,
        github_source: GitHubSource | None = None,
    ) -> None:
        self.settings = settings or config.load_settings()
        self.store = store or OrchestratorStore()
        self._signals = signals
        self._schedule_port = schedule
        self._issue_tracker_port = issue_tracker
        self._cloud_factory = cloud_factory or _default_cloud
        self._agent_factory = agent_factory or _default_agent
        self.workspace = str(
            Path(workspace_root).expanduser().resolve()
            if workspace_root
            else config.workspace_root(self.settings)
        )
        self.owner = (
            owner or f"{os.getpid()}@{os.uname().nodename if hasattr(os, 'uname') else 'local'}"
        )
        self.policy = ApprovalPolicy(
            rejection_limit=rejection_limit or self.settings.approval_rejection_limit
        )
        self.clock = clock or utcnow
        self._github = github_source

    # -- dependency helpers ---------------------------------------------

    def _sink(self) -> SignalSink:
        if self._signals is None:
            self._signals = OdiSignalAdapter()
        return self._signals

    def _schedule(self) -> SchedulePort:
        if self._schedule_port is None:
            self._schedule_port = OdiScheduleAdapter()
        return self._schedule_port

    def _issue_tracker(self) -> IssueTrackerPort:
        if self._issue_tracker_port is None:
            from agentic_odi_integrations_openhands.config import load_settings

            settings = load_settings()
            self._issue_tracker_port = GitHubIssueTracker(settings.github)
        return self._issue_tracker_port

    def _now(self) -> datetime:
        return self.clock().astimezone(timezone.utc)

    # -- public reads ----------------------------------------------------

    def targets(self) -> list[AgentTarget]:
        return list(self.settings.targets)

    def require_target(self, alias: str | None) -> AgentTarget:
        target = self.settings.target(alias)
        if target is None:
            known = ", ".join(t.alias for t in self.settings.targets) or "none configured"
            raise TargetNotConfigured(
                f"No OpenHands target {alias!r}. Configure one in {config.config_path()} "
                f"(known targets: {known})."
            )
        if not target.enabled:
            raise TargetNotConfigured(f"Target {target.alias!r} is disabled.")
        if not target.resolved_api_key:
            raise TargetNotConfigured(
                f"Target {target.alias!r} has no API key. Set {target.api_key_env} "
                "in the environment or add api_key to the target."
            )
        return target

    def list_work_items(
        self, status: WorkItemStatus | str | None = None, source_kind: str | None = None
    ) -> list[WorkItem]:
        self.store.refresh()
        return self.store.list_work_items(status=status, source_kind=source_kind)

    def get_work_item(self, work_id: str) -> WorkItem:
        self.store.refresh()
        work = self.store.get_work_item(work_id)
        if work is None:
            raise WorkItemNotFound(f"work item not found: {work_id}")
        return work

    def list_runs(self, work_id: str | None = None) -> list[AgentRun]:
        self.store.refresh()
        if work_id is not None:
            self.get_work_item(work_id)
        return self.store.list_runs(work_id)

    def get_run(self, run_id: str) -> AgentRun:
        self.store.refresh()
        run = self.store.get_run(run_id)
        if run is None:
            raise WorkItemNotFound(f"agent run not found: {run_id}")
        return run

    def latest_run(self, work_id: str) -> AgentRun | None:
        self.get_work_item(work_id)
        return self.store.latest_run(work_id)

    def approvals(self, run_id: str) -> list[ApprovalRecord]:
        self.store.refresh()
        return self.store.approvals_for_run(run_id)

    def status(self) -> OrchestratorStatus:
        self.store.refresh()
        counts = self.store.counts()
        heartbeat_at, pid, running = _read_heartbeat(
            config.heartbeat_path(self.settings), self.settings.poll_interval_s
        )
        return OrchestratorStatus(
            daemon_running=running,
            heartbeat_at=heartbeat_at,
            pid=pid,
            queued=counts.get(WorkItemStatus.QUEUED.value, 0),
            running=counts.get(WorkItemStatus.RUNNING.value, 0)
            + counts.get(WorkItemStatus.DISPATCHING.value, 0),
            waiting_for_confirmation=counts.get(WorkItemStatus.WAITING_FOR_CONFIRMATION.value, 0),
            completed=counts.get(WorkItemStatus.COMPLETED.value, 0),
            failed=counts.get(WorkItemStatus.FAILED.value, 0),
            blocked=counts.get(WorkItemStatus.BLOCKED.value, 0),
            cancelled=counts.get(WorkItemStatus.CANCELLED.value, 0),
            targets=[target.alias for target in self.settings.targets if target.enabled],
            db_path=str(self.store.path),
            config_path=str(config.config_path()),
        )

    # -- public writes ---------------------------------------------------

    def add_work_item(
        self,
        title: str,
        prompt: str,
        *,
        target_alias: str | None = None,
        repository: str | None = None,
        branch: str | None = None,
        priority: int = 0,
        work_key: str | None = None,
        source_kind: SourceKind | str = SourceKind.MANUAL,
        source_ref: str | None = None,
        job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[WorkItem, bool]:
        self.store.refresh()
        if not title.strip():
            raise ValueError("work item title must not be empty")
        if not prompt.strip():
            raise ValueError("work item prompt must not be empty")
        source = SourceKind(source_kind) if isinstance(source_kind, str) else source_kind
        key = work_key or f"{source.value}:{uuid.uuid4()}"
        existing = self.store.get_work_item_by_key(key)
        if existing is not None:
            return existing, False
        target = self.require_target(target_alias)
        work = WorkItem(
            work_key=key,
            source_kind=source,
            source_ref=source_ref,
            title=title.strip(),
            prompt=prompt.strip(),
            target_alias=target.alias,
            repository=repository or target.repository,
            branch=branch or target.branch,
            priority=priority,
            job_id=job_id,
            metadata=metadata or {},
            next_attempt_at=self._now(),
        )
        return self.store.add_work_item(work)

    def cancel_work_item(self, work_id: str) -> WorkItem:
        work = self.get_work_item(work_id)
        if work.is_terminal:
            raise InvalidTransition(f"{work_id} is already {work.status.value}")
        self.store.update_work_item(work_id, {"status": WorkItemStatus.CANCELLED})
        run = self.store.latest_run(work_id)
        if run is not None and not run.is_terminal:
            self.store.update_run(run.id, {"cancel_requested_at": self._now()})
        return self.get_work_item(work_id)

    def retry_work_item(self, work_id: str) -> WorkItem:
        work = self.get_work_item(work_id)
        if not work.is_terminal:
            raise InvalidTransition(f"{work_id} is still {work.status.value}")
        manual_retries = int(work.metadata.get("manual_retries", 0)) + 1
        metadata = {**work.metadata, "manual_retries": manual_retries}
        self.store.update_work_item(
            work_id,
            {
                "status": WorkItemStatus.QUEUED,
                "attempts": 0,
                "next_attempt_at": self._now(),
                "metadata": metadata,
            },
        )
        return self.get_work_item(work_id)

    # -- daemon loop -----------------------------------------------------

    def recover(self) -> list[str]:
        """Adopt work a previous daemon left running; never re-POST blindly."""
        self.store.refresh()
        notes: list[str] = []
        for run in self.store.active_runs():
            work = self.store.get_work_item(run.work_item_id)
            if work is None:
                continue
            if run.conversation_id:
                self.store.update_run(
                    run.id,
                    {
                        "lease_owner": self.owner,
                        "lease_expires_at": self._now()
                        + timedelta(seconds=self.settings.lease_seconds),
                    },
                )
                notes.append(f"adopted conversation {run.conversation_id}")
                continue
            if run.start_task_id:
                notes.append(f"adopted start task {run.start_task_id}")
                continue
            try:
                target = self.require_target(work.target_alias)
            except TargetNotConfigured as exc:
                self._block(run, work, str(exc))
                continue
            self._adopt_by_title(run, work, target)
            notes.append(f"recovered run {run.id}")
        return notes

    def tick(self) -> TickReport:
        now = self._now()
        report = TickReport()
        self.store.refresh()
        report.enqueued_schedules = self._enqueue_due_schedules(now)
        self._poll_github(now, report)
        report.issues_created = self._poll_issues(now, report)
        report.automation_adopted = self._poll_automation(now, report)
        self._supervise_active(now, report)
        self._dispatch_queued(now, report)
        return report

    def run_once(self) -> TickReport:
        self.recover()
        return self.tick()

    # -- GitHub intake ---------------------------------------------------

    def _github_source(self) -> GitHubSource:
        if self._github is None:
            from agentic_odi_integrations_openhands.github_source import GitHubSource

            self._github = GitHubSource(self.settings.github)
        return self._github

    def _poll_github(self, now: datetime, report: TickReport) -> None:
        if not self.settings.github.enabled or not self.settings.github.repos:
            return
        try:
            report.github_created = self._github_source().poll(self, now.timestamp())
        except Exception as exc:  # noqa: BLE001 - intake failure must not stop the daemon
            report.errors.append(f"github: {exc}")

    def _poll_issues(self, now: datetime, report: TickReport) -> int:
        """Poll issue trackers for new ODI-labelled issues and queue them as work."""
        if not self.settings.github.enabled or not self.settings.github.repos:
            return 0
        created = 0
        try:
            tracker = self._issue_tracker()
            issues = tracker.due_issues()
        except Exception as exc:  # noqa: BLE001 - intake failure must not stop the daemon
            report.errors.append(f"issues: {exc}")
            return 0
        for issue in issues:
            work_key = f"issue:{issue.id}"
            existing = self.store.get_work_item_by_key(work_key)
            if existing is not None:
                continue
            try:
                _, was_created = self.add_work_item(
                    title=issue.title,
                    prompt=issue.body or issue.title,
                    target_alias=self.settings.default_target,
                    repository=issue.repository,
                    branch=None,
                    work_key=work_key,
                    source_kind=SourceKind.GITHUB,
                    source_ref=str(issue.number),
                    metadata={
                        "issue_number": issue.number,
                        "issue_url": issue.url,
                        "issue_state": issue.state,
                        "issue_labels": issue.labels,
                    },
                )
                created += int(was_created)
            except (OrchestratorError, ValueError) as exc:
                report.errors.append(f"issue {issue.id}: {exc}")
                continue
        report.issues_created = created
        return created

    def _poll_automation(self, now: datetime, report: TickReport) -> int:
        """Adopt existing OpenHands Automation conversations as tracked work.

        Fail-closed: only adopts conversations that already exist; never
        starts a new conversation. Matches by repo pattern against the
        conversation's repo field. Dedupe by automation:{conversation.id}.
        """
        if not self.settings.automation.enabled:
            return 0
        if not self.settings.automation.repo_patterns:
            return 0

        adopted = 0
        for target in self.settings.targets:
            conversations = self._search_automation_conversations(target)
            for conv in conversations:
                if not conv.repo:
                    continue
                if not any(
                    fnmatch.fnmatch(conv.repo, pat)
                    for pat in self.settings.automation.repo_patterns
                ):
                    continue
                work_key = f"automation:{conv.id}"
                existing = self.store.get_work_item_by_key(work_key)
                if existing is not None:
                    continue
                try:
                    _, was_created = self.add_work_item(
                        title=conv.title or f"Automation: {conv.id}",
                        prompt=(
                            f"Adopted OpenHands Automation conversation {conv.id} "
                            f"for repo {conv.repo}."
                        ),
                        target_alias=target.alias,
                        repository=conv.repo,
                        branch=conv.branch,
                        work_key=work_key,
                        source_kind=SourceKind.AUTOMATION,
                        source_ref=conv.id,
                        metadata={
                            "automation_conversation_id": conv.id,
                            "automation_conversation_url": conv.conversation_url,
                            "automation_repo": conv.repo,
                            "automation_branch": conv.branch,
                        },
                    )
                    adopted += int(was_created)
                except (OrchestratorError, ValueError) as exc:
                    report.errors.append(f"automation {conv.id}: {exc}")
                    continue
        report.automation_adopted = adopted
        return adopted

    def _search_automation_conversations(self, target: AgentTarget) -> list[ConversationInfo]:
        """Search for Automation conversations for one target.

        Returns an empty list on any error so one target never blocks another.
        """
        try:
            client = self._cloud_factory(target)
            return client.search_conversations(title_contains=self.settings.automation.label)
        except Exception:  # noqa: BLE001 - one target must not block adoption
            return []

    # -- schedules -------------------------------------------------------

    def _enqueue_due_schedules(self, now: datetime) -> int:
        try:
            sched = self._schedule()
            schedules = sched.list_scheduled_work(status=ScheduledWorkStatus.SCHEDULED.value)
        except Exception:  # noqa: BLE001 - the ODI store is optional for manual-only use
            return 0
        created = 0
        for schedule in schedules:
            due_at = schedule.trigger_requested_at or schedule.next_run_at
            if not due_at:
                continue
            try:
                if datetime.fromisoformat(due_at.replace("Z", "+00:00")) > now:
                    continue
            except ValueError:
                continue
            payload = schedule.payload or {}
            try:
                target_alias = (
                    payload.get("target")
                    or payload.get("target_alias")
                    or self.settings.default_target
                )
                title = str(payload.get("title") or schedule.name)
                prompt = str(payload.get("prompt") or payload.get("message") or schedule.name)
                _, was_created = self.add_work_item(
                    title,
                    prompt,
                    target_alias=target_alias,
                    repository=payload.get("repository"),
                    branch=payload.get("branch"),
                    work_key=f"schedule:{schedule.id}:{due_at}",
                    source_kind=SourceKind.SCHEDULE,
                    source_ref=schedule.id,
                    job_id=schedule.job_id,
                    metadata={"schedule_name": schedule.name, "scheduled_for": due_at},
                )
            except (OrchestratorError, ValueError) as exc:
                sched.update_scheduled_work(
                    schedule.id,
                    {"result_summary": f"Could not queue: {exc}", "last_run_at": now.isoformat()},
                )
                continue
            updates: dict[str, Any] = {
                "trigger_requested_at": None,
                "last_run_at": now.isoformat(),
            }
            next_at = next_occurrence(schedule.schedule_expression, now)
            if next_at is not None:
                updates["next_run_at"] = next_at.isoformat()
                updates["status"] = ScheduledWorkStatus.SCHEDULED
            else:
                updates["next_run_at"] = None
                updates["status"] = ScheduledWorkStatus.RUNNING
            updates["result_summary"] = "Queued for the orchestrator; no result yet."
            sched.update_scheduled_work(schedule.id, updates)
            created += int(was_created)
        return created

    def _sync_schedule_terminal(self, work: WorkItem, run: AgentRun) -> None:
        if work.source_kind is not SourceKind.SCHEDULE or not work.source_ref:
            return
        try:
            sched = self._schedule()
            schedule = sched.get_scheduled_work(work.source_ref)
            if schedule is None:
                return
            status = {
                AgentRunStatus.COMPLETED: ScheduledWorkStatus.COMPLETED,
                AgentRunStatus.FAILED: ScheduledWorkStatus.FAILED,
                AgentRunStatus.BLOCKED: ScheduledWorkStatus.FAILED,
                AgentRunStatus.CANCELLED: ScheduledWorkStatus.CANCELLED,
            }[run.status]
            if schedule.trigger_type.value == "cron":
                status = ScheduledWorkStatus.SCHEDULED
            summary = run.summary or run.error or run.blocked_reason or run.status.value
            sched.update_scheduled_work(
                schedule.id,
                {
                    "status": status,
                    "last_run_at": (run.finished_at or self._now()).isoformat(),
                    "result_summary": summary[:500],
                },
            )
        except Exception:  # noqa: BLE001 - reporting must not break supervision
            return

    def _github_notify(self, work: WorkItem, run: AgentRun) -> None:
        if work.source_kind is not SourceKind.GITHUB or not self.settings.github.enabled:
            return
        try:
            from agentic_odi_integrations_openhands.github_source import GitHubNotifier

            GitHubNotifier(self.settings.github).notify_terminal(work, run)
        except Exception:  # noqa: BLE001 - GitHub is a mirror, not the source of truth
            return

    # -- dispatch --------------------------------------------------------

    def _active_for_target(self, alias: str) -> int:
        count = 0
        for run in self.store.active_runs():
            work = self.store.get_work_item(run.work_item_id)
            if work is not None and work.target_alias == alias:
                count += 1
        return count

    def _dispatch_queued(self, now: datetime, report: TickReport) -> None:
        reported: set[str] = set()
        for work in self.store.due_work_items(now):
            try:
                target = self.require_target(work.target_alias)
            except TargetNotConfigured as exc:
                self._finish_work(work, WorkItemStatus.FAILED, error=str(exc), signal=True)
                report.errors.append(str(exc))
                continue
            budget = self._budget_reason(target, now)
            if budget is not None:
                if budget not in reported:
                    report.errors.append(budget)
                    reported.add(budget)
                continue
            if self._active_for_target(target.alias) >= target.max_concurrency:
                continue
            if self.settings.max_concurrency is not None:
                if len(self.store.active_runs()) >= self.settings.max_concurrency:
                    continue
            self._start(work, target, now, report)

    def _budget_reason(self, target: AgentTarget, now: datetime) -> str | None:
        """Stop new dispatch when a UTC-day cap is reached; active runs continue."""
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if target.daily_cost_limit_usd is not None:
            spent = self.store.spent_since(day_start, target.alias)
            if spent >= target.daily_cost_limit_usd:
                return (
                    f"{target.alias}: daily cost limit "
                    f"${target.daily_cost_limit_usd:.2f} reached (spent ${spent:.2f}); "
                    "new work waits for tomorrow"
                )
        if self.settings.daily_cost_limit_usd is not None:
            spent = self.store.spent_since(day_start)
            if spent >= self.settings.daily_cost_limit_usd:
                return (
                    f"daily cost limit ${self.settings.daily_cost_limit_usd:.2f} reached "
                    f"(spent ${spent:.2f}); new work waits for tomorrow"
                )
        return None

    def _start(
        self, work: WorkItem, target: AgentTarget, now: datetime, report: TickReport
    ) -> AgentRun:
        run = AgentRun(
            work_item_id=work.id,
            attempt=work.attempts + 1,
            status=AgentRunStatus.PENDING,
            lease_owner=self.owner,
            lease_expires_at=now + timedelta(seconds=self.settings.lease_seconds),
            started_at=now,
        )
        self.store.add_run(run)
        self.store.update_work_item(
            work.id,
            {"status": WorkItemStatus.DISPATCHING, "attempts": work.attempts + 1},
        )
        try:
            client = self._cloud_factory(target)
            task = client.start_conversation(
                self._prompt_for(work),
                repository=work.repository,
                branch=work.branch,
                llm_model=target.llm_model,
                agent_profile_id=target.agent_profile_id,
                agent_type=target.agent_type,
                plugins=target.plugins or None,
                title=f"[odi:{work.id}] {work.title}"[:120],
                system_message_suffix=target.system_message_suffix or DEFAULT_BOUNDARY,
                observability_metadata={
                    "odi_work_id": work.id,
                    "odi_run_id": run.id,
                    "odi_source": work.source_kind.value,
                    "odi_work_key": work.work_key,
                },
                observability_tags=["odi", f"odi-{work.source_kind.value}"],
            )
        except Exception as exc:  # noqa: BLE001 - classified below
            self._fail_run(run, work, target, exc, retryable=_transient(exc))
            report.errors.append(str(exc))
            return run

        run = self.store.update_run(
            run.id,
            {
                "start_task_id": task.id,
                "status": AgentRunStatus.STARTING,
                "last_polled_at": now,
            },
        )
        report.dispatched += 1
        if task.failed:
            self._fail_run(
                run,
                work,
                target,
                RuntimeError(task.error_message),
                retryable=_transient_start_error(task.error_message),
            )
        elif task.ready:
            self._become_ready(run, work, target, client, task)
        return run

    def _prompt_for(self, work: WorkItem) -> str:
        return (
            f"{work.prompt}\n\n---\nOrchestrator brief\n"
            f"- Repository: {work.repository or 'the selected repository'}\n"
            f"- Branch: {work.branch or 'create a feature branch'}\n"
            f"- {DEFAULT_BOUNDARY}\n"
        )

    def _become_ready(
        self,
        run: AgentRun,
        work: WorkItem,
        target: AgentTarget,
        client: CloudClient,
        task: StartTask,
    ) -> AgentRun:
        conversation_id = task.resolved_conversation_id
        if not conversation_id:
            return self._adopt_by_title(run, work, target)
        try:
            info = client.get_conversation(conversation_id)
        except Exception as exc:  # noqa: BLE001
            self._fail_run(run, work, target, exc, retryable=_transient(exc))
            return run
        run = self.store.update_run(
            run.id,
            {
                "conversation_id": info.id or conversation_id,
                "sandbox_id": info.sandbox_id,
                "conversation_url": info.conversation_url,
                "session_api_key": info.session_api_key,
                "status": AgentRunStatus.RUNNING,
                "lease_owner": self.owner,
                "lease_expires_at": self._now() + timedelta(seconds=self.settings.lease_seconds),
            },
        )
        policy_ok = self._set_policy(run, target)
        if not policy_ok:
            self._block(run, work, "could not install the confirmation policy")
            return run
        self.store.update_work_item(work.id, {"status": WorkItemStatus.RUNNING})
        return run

    def _set_policy(self, run: AgentRun, target: AgentTarget) -> bool:
        if not run.conversation_id or not run.conversation_url:
            return False
        try:
            agent = self._agent_factory(run.conversation_url, run.session_api_key)
            agent.set_confirmation_policy(run.conversation_id, target.confirmation())
        except Exception:  # noqa: BLE001 - fail closed
            return False
        self.store.update_run(run.id, {"policy_verified": True})
        return True

    def _adopt_by_title(self, run: AgentRun, work: WorkItem, target: AgentTarget) -> AgentRun:
        client = self._cloud_factory(target)
        try:
            matches = client.search_conversations(f"[odi:{work.id}]")
        except Exception as exc:  # noqa: BLE001
            self._fail_run(run, work, target, exc, retryable=_transient(exc))
            return run
        if len(matches) != 1:
            reason = (
                "no matching conversation after a restart; refusing to dispatch a duplicate"
                if not matches
                else f"{len(matches)} matching conversations after a restart; refusing to guess"
            )
            self._block(run, work, reason)
            return run
        info = matches[0]
        run = self.store.update_run(
            run.id,
            {
                "conversation_id": info.id,
                "sandbox_id": info.sandbox_id,
                "conversation_url": info.conversation_url,
                "session_api_key": info.session_api_key,
                "status": AgentRunStatus.RUNNING,
                "lease_owner": self.owner,
                "lease_expires_at": self._now() + timedelta(seconds=self.settings.lease_seconds),
            },
        )
        if not self._set_policy(run, target):
            self._block(run, work, "could not install the confirmation policy")
            return run
        self.store.update_work_item(work.id, {"status": WorkItemStatus.RUNNING})
        return run

    # -- supervision -----------------------------------------------------

    def _supervise_active(self, now: datetime, report: TickReport) -> None:
        for run in self.store.active_runs():
            work = self.store.get_work_item(run.work_item_id)
            if work is None:
                continue
            if run.cancel_requested_at is not None:
                self._stop(run, work)
                report.terminal += 1
                continue
            try:
                target = self.require_target(work.target_alias)
            except TargetNotConfigured as exc:
                self._block(run, work, str(exc))
                report.terminal += 1
                continue
            if run.started_at and (now - run.started_at).total_seconds() > target.max_runtime_s:
                self._stop_and_fail(
                    run, work, f"run exceeded the {target.max_runtime_s}s wall clock limit"
                )
                report.terminal += 1
                continue
            if run.cost_usd > target.max_cost_usd:
                self._stop_and_fail(
                    run, work, f"run exceeded the ${target.max_cost_usd:.2f} cost limit"
                )
                report.terminal += 1
                continue
            before = run.status
            try:
                if run.status in {AgentRunStatus.PENDING, AgentRunStatus.STARTING}:
                    run = self._advance_start(run, work, target)
                else:
                    run = self._advance_running(run, work, target)
            except Exception as exc:  # noqa: BLE001 - a poll failure must not kill the loop
                report.errors.append(f"{run.id}: {exc}")
                run = self.store.update_run(
                    run.id,
                    {
                        "lease_owner": self.owner,
                        "lease_expires_at": now + timedelta(seconds=self.settings.lease_seconds),
                    },
                )
            report.supervised += 1
            if run.is_terminal and before not in {
                AgentRunStatus.COMPLETED,
                AgentRunStatus.FAILED,
                AgentRunStatus.BLOCKED,
                AgentRunStatus.CANCELLED,
            }:
                report.terminal += 1

    def _advance_start(self, run: AgentRun, work: WorkItem, target: AgentTarget) -> AgentRun:
        if not run.start_task_id:
            return self._adopt_by_title(run, work, target)
        client = self._cloud_factory(target)
        task = client.get_start_task(run.start_task_id)
        if task is None:
            self._fail_run(
                run, work, target, RuntimeError("start task disappeared"), retryable=True
            )
            return self.store.get_run(run.id) or run
        if task.in_flight:
            return self.store.update_run(
                run.id,
                {
                    "lease_owner": self.owner,
                    "lease_expires_at": self._now()
                    + timedelta(seconds=self.settings.lease_seconds),
                    "last_polled_at": self._now(),
                },
            )
        if task.failed:
            self._fail_run(
                run,
                work,
                target,
                RuntimeError(task.error_message),
                retryable=_transient_start_error(task.error_message),
            )
            return self.store.get_run(run.id) or run
        return self._become_ready(run, work, target, client, task)

    def _advance_running(self, run: AgentRun, work: WorkItem, target: AgentTarget) -> AgentRun:
        if not run.conversation_id or not run.conversation_url:
            return self._adopt_by_title(run, work, target)
        agent = self._agent_factory(run.conversation_url, run.session_api_key)
        info = agent.get_conversation(run.conversation_id)
        cost, tokens = _cost_and_tokens(info)
        run = self.store.update_run(
            run.id,
            {
                "cost_usd": cost,
                "tokens": tokens,
                "lease_owner": self.owner,
                "lease_expires_at": self._now() + timedelta(seconds=self.settings.lease_seconds),
                "last_polled_at": self._now(),
            },
        )
        if cost > target.max_cost_usd:
            self._stop_and_fail(
                run, work, f"run exceeded the ${target.max_cost_usd:.2f} cost limit"
            )
            return self.store.get_run(run.id) or run

        if info.has_blocked_actions:
            self._block(run, work, "an OpenHands hook blocked an action")
            return self.store.get_run(run.id) or run

        status = info.execution
        if status is ExecutionStatus.FINISHED:
            self._complete(run, work, info)
            return self.store.get_run(run.id) or run
        if status in {ExecutionStatus.ERROR, ExecutionStatus.STUCK}:
            message = f"conversation ended in {status.value}" if status else "unknown error"
            self._fail_run(run, work, target, RuntimeError(message), retryable=True)
            return self.store.get_run(run.id) or run
        if status is ExecutionStatus.PAUSED or info.sandbox is SandboxStatus.PAUSED:
            if run.resumes >= 1:
                self._fail_run(
                    run, work, target, RuntimeError("sandbox paused twice"), retryable=True
                )
                return self.store.get_run(run.id) or run
            client = self._cloud_factory(target)
            if run.sandbox_id:
                try:
                    client.resume_sandbox(run.sandbox_id)
                except Exception as exc:  # noqa: BLE001
                    self._fail_run(run, work, target, exc, retryable=_transient(exc))
                    return self.store.get_run(run.id) or run
            return self.store.update_run(run.id, {"resumes": run.resumes + 1})
        if status is ExecutionStatus.WAITING_FOR_CONFIRMATION:
            return self._handle_confirmations(run, work, target, agent)
        if status is ExecutionStatus.DELETING:
            self._block(run, work, "the conversation is being deleted")
            return self.store.get_run(run.id) or run
        if work.status is WorkItemStatus.WAITING_FOR_CONFIRMATION:
            self.store.update_work_item(work.id, {"status": WorkItemStatus.RUNNING})
        return self.store.update_run(
            run.id,
            {"status": AgentRunStatus.RUNNING},
        )

    def _handle_confirmations(
        self,
        run: AgentRun,
        work: WorkItem,
        target: AgentTarget,
        agent: ConversationAgent,
    ) -> AgentRun:
        events = self._fetch_events(agent, run.conversation_id or "")
        pending = pending_actions(events)
        if not pending:
            return self.store.update_run(
                run.id, {"status": AgentRunStatus.WAITING_FOR_CONFIRMATION}
            )
        self.store.update_work_item(work.id, {"status": WorkItemStatus.WAITING_FOR_CONFIRMATION})
        decided = {
            record.tool_call_id
            for record in self.store.approvals_for_run(run.id)
            if record.tool_call_id
        }
        for action in pending:
            if action.tool_call_id and action.tool_call_id in decided:
                continue
            decision = self._decide(action, work, target, run)
            accept = decision.decision is Decision.ACCEPT
            reason = None if accept else decision.reason
            try:
                agent.respond_to_confirmation(run.conversation_id or "", action.id, accept, reason)
            except Exception as exc:  # noqa: BLE001 - retried next tick, decision not recorded
                return self.store.update_run(run.id, {"error": f"confirmation failed: {exc}"})
            self.store.record_approval(
                ApprovalRecord(
                    run_id=run.id,
                    conversation_id=run.conversation_id,
                    action_id=action.id,
                    tool_call_id=action.tool_call_id or None,
                    tool_name=action.tool_name,
                    risk=action.security_risk,
                    decision=decision.decision,
                    rule_id=decision.rule_id,
                    reason=decision.reason,
                    args_digest=args_digest(action.arguments),
                )
            )
            if accept:
                run = self.store.update_run(run.id, {"approvals": run.approvals + 1})
                continue
            run = self.store.update_run(run.id, {"rejections": run.rejections + 1})
            if decision.decision is Decision.BLOCK or run.rejections >= self.policy.rejection_limit:
                self._block(run, work, decision.reason)
                return self.store.get_run(run.id) or run
        return self.store.update_run(run.id, {"status": AgentRunStatus.WAITING_FOR_CONFIRMATION})

    def _decide(
        self, action: ActionEvent, work: WorkItem, target: AgentTarget, run: AgentRun
    ) -> PolicyDecision:
        request = ActionRequest(
            tool_name=action.tool_name,
            arguments=action.arguments,
            risk=action.security_risk,
            repository=work.repository,
            default_branch=work.branch,
            workspace_root=self.workspace,
        )
        return self.policy.evaluate(request, prior_rejections=run.rejections)

    def _fetch_events(self, agent: ConversationAgent, conversation_id: str) -> list[Event]:
        events: list[Event] = []
        page_id: str | None = None
        for _ in range(5):
            page = agent.search_events(conversation_id, page_id=page_id, limit=100)
            events.extend(page.items)
            page_id = page.next_page_id
            if not page_id:
                break
        return events

    # -- terminal transitions -------------------------------------------

    def _complete(self, run: AgentRun, work: WorkItem, info: ConversationInfo) -> None:
        try:
            agent = self._agent_factory(run.conversation_url or "", run.session_api_key)
            events = self._fetch_events(agent, run.conversation_id or "")
        except Exception:  # noqa: BLE001 - metrics still make a truthful terminal state
            events = []
        summary = final_message(events) or "Agent finished with no summary."
        urls = pr_urls(summary)
        for url in pr_urls(json.dumps(info.metrics or {})):
            if url not in urls:
                urls.append(url)
        cost, tokens = _cost_and_tokens(info)
        finished = self._now()
        self.store.update_run(
            run.id,
            {
                "status": AgentRunStatus.COMPLETED,
                "summary": summary[:4000],
                "pr_urls": urls,
                "cost_usd": cost or run.cost_usd,
                "tokens": tokens or run.tokens,
                "finished_at": finished,
                "lease_expires_at": finished,
            },
        )
        self.store.update_work_item(work.id, {"status": WorkItemStatus.COMPLETED})
        self._finish_side_effects(work, self.store.get_run(run.id) or run)

    def _fail_run(
        self,
        run: AgentRun,
        work: WorkItem,
        target: AgentTarget,
        exc: Exception,
        *,
        retryable: bool,
    ) -> None:
        message = str(exc) or exc.__class__.__name__
        finished = self._now()
        self.store.update_run(
            run.id,
            {
                "status": AgentRunStatus.FAILED,
                "error": message[:2000],
                "finished_at": finished,
                "lease_expires_at": finished,
            },
        )
        if retryable and work.attempts < target.max_attempts:
            delay = min(60 * (2 ** max(work.attempts - 1, 0)), 900)
            self.store.update_work_item(
                work.id,
                {
                    "status": WorkItemStatus.QUEUED,
                    "next_attempt_at": finished + timedelta(seconds=delay),
                },
            )
            return
        self.store.update_work_item(work.id, {"status": WorkItemStatus.FAILED})
        self._finish_side_effects(work, self.store.get_run(run.id) or run)

    def _stop_and_fail(self, run: AgentRun, work: WorkItem, reason: str) -> None:
        self._stop_remote(run)
        finished = self._now()
        self.store.update_run(
            run.id,
            {
                "status": AgentRunStatus.FAILED,
                "error": reason,
                "finished_at": finished,
                "lease_expires_at": finished,
            },
        )
        self.store.update_work_item(work.id, {"status": WorkItemStatus.FAILED})
        self._finish_side_effects(work, self.store.get_run(run.id) or run)

    def _block(self, run: AgentRun, work: WorkItem, reason: str) -> None:
        self._stop_remote(run)
        finished = self._now()
        self.store.update_run(
            run.id,
            {
                "status": AgentRunStatus.BLOCKED,
                "blocked_reason": reason[:2000],
                "finished_at": finished,
                "lease_expires_at": finished,
            },
        )
        self.store.update_work_item(work.id, {"status": WorkItemStatus.BLOCKED})
        self._finish_side_effects(work, self.store.get_run(run.id) or run)

    def _stop(self, run: AgentRun, work: WorkItem) -> None:
        self._stop_remote(run)
        finished = self._now()
        self.store.update_run(
            run.id,
            {
                "status": AgentRunStatus.CANCELLED,
                "finished_at": finished,
                "lease_expires_at": finished,
            },
        )
        self.store.update_work_item(work.id, {"status": WorkItemStatus.CANCELLED})

    def _stop_remote(self, run: AgentRun) -> None:
        """Best-effort stop. A failed stop is reported by the next poll, not hidden."""
        try:
            if run.sandbox_id:
                target = self.store.get_work_item(run.work_item_id)
                alias = target.target_alias if target else None
                configured = self.settings.target(alias)
                if configured is not None:
                    client = self._cloud_factory(configured)
                    try:
                        client.pause_sandbox(run.sandbox_id)
                    finally:
                        client.delete_sandbox(run.sandbox_id)
            elif run.conversation_url and run.conversation_id:
                agent = self._agent_factory(run.conversation_url, run.session_api_key)
                agent.pause_conversation(run.conversation_id)
                agent.delete_conversation(run.conversation_id)
        except Exception:  # noqa: BLE001 - the local terminal state is still recorded
            return

    def _finish_works(self, work: WorkItem, status: WorkItemStatus, **changes: Any) -> None:
        self.store.update_work_item(work.id, {"status": status, **changes})

    def _finish_work(
        self,
        work: WorkItem,
        status: WorkItemStatus,
        *,
        error: str | None = None,
        signal: bool,
    ) -> None:
        changes: dict[str, Any] = {"status": status}
        if error:
            changes["error"] = error
        self.store.update_work_item(work.id, changes)
        if signal:
            # No run exists for a configuration failure; record a synthetic one so
            # the signal points at something the Work panel can show.
            run = AgentRun(
                work_item_id=work.id,
                attempt=max(work.attempts, 1),
                status=AgentRunStatus.FAILED
                if status is WorkItemStatus.FAILED
                else AgentRunStatus.BLOCKED,
                error=error,
                blocked_reason=error if status is WorkItemStatus.BLOCKED else None,
                started_at=self._now(),
                finished_at=self._now(),
            )
            self.store.add_run(run)
            self._finish_side_effects(work, run)

    def _finish_side_effects(self, work: WorkItem, run: AgentRun) -> None:
        refreshed = self.store.get_work_item(work.id) or work
        if not run.signal_sent:
            try:
                terminal_signal(self._sink(), refreshed, run)
            except Exception:  # noqa: BLE001  # nosec B110
                # A failed signal must not undo the recorded result.
                pass
            self.store.update_run(run.id, {"signal_sent": True})
        self._sync_schedule_terminal(refreshed, run)
        self._github_notify(refreshed, run)


def _read_heartbeat(path: Path, interval_s: int) -> tuple[datetime | None, int | None, bool]:
    if not path.exists():
        return None, None, False
    try:
        payload = json.loads(path.read_text())
        stamp = datetime.fromisoformat(str(payload.get("timestamp", "")).replace("Z", "+00:00"))
        pid = int(payload.get("pid")) if payload.get("pid") is not None else None
    except (OSError, ValueError, TypeError):
        return None, None, False
    fresh = (utcnow() - stamp.astimezone(timezone.utc)).total_seconds() < max(interval_s * 3, 60)
    alive = True
    if pid is not None:
        try:
            os.kill(pid, 0)
        except OSError:
            alive = False
    return stamp, pid, fresh and alive


def write_heartbeat(path: Path, counts: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **counts,
    }
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(serialize(payload)))
    os.replace(tmp, path)


def sleep_until_next(interval_s: int, stop: Callable[[], bool] | None = None) -> None:
    """Sleep in short slices so a signal handler can stop the loop promptly."""
    deadline = time.monotonic() + interval_s
    while time.monotonic() < deadline:
        if stop is not None and stop():
            return
        time.sleep(min(0.2, max(deadline - time.monotonic(), 0)))
