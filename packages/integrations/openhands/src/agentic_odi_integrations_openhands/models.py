"""Orchestrator domain models.

Every field the daemon needs to resume after a crash is persisted, including
the dispatch token written before the Cloud POST and the conversation's
session key. ``session_api_key`` is deliberately part of the persisted model
(so supervision survives a restart) but never part of a public dump.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from agentic_odi_openhands.models import (
    AlwaysConfirm,
    ConfirmationPolicy,
    ConfirmRisky,
    NeverConfirm,
    SecurityRisk,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class WorkItemStatus(str, Enum):
    QUEUED = "queued"
    DISPATCHING = "dispatching"
    RUNNING = "running"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


TERMINAL_WORK_STATUSES = frozenset(
    {
        WorkItemStatus.COMPLETED,
        WorkItemStatus.FAILED,
        WorkItemStatus.BLOCKED,
        WorkItemStatus.CANCELLED,
    }
)
ACTIVE_WORK_STATUSES = frozenset(
    {
        WorkItemStatus.DISPATCHING,
        WorkItemStatus.RUNNING,
        WorkItemStatus.WAITING_FOR_CONFIRMATION,
    }
)


class AgentRunStatus(str, Enum):
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


TERMINAL_RUN_STATUSES = frozenset(
    {
        AgentRunStatus.COMPLETED,
        AgentRunStatus.FAILED,
        AgentRunStatus.BLOCKED,
        AgentRunStatus.CANCELLED,
    }
)
ACTIVE_RUN_STATUSES = frozenset(
    {
        AgentRunStatus.PENDING,
        AgentRunStatus.STARTING,
        AgentRunStatus.RUNNING,
        AgentRunStatus.WAITING_FOR_CONFIRMATION,
    }
)


class SourceKind(str, Enum):
    MANUAL = "manual"
    GITHUB = "github"
    SCHEDULE = "schedule"
    STUDIO = "studio"
    AUTOMATION = "automation"


class Decision(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    BLOCK = "block"


class AgentTarget(BaseModel):
    """One OpenHands deployment plus the agent profile used on it."""

    model_config = ConfigDict(extra="allow")

    alias: str
    base_url: str
    api_key_env: str = "OPENHANDS_API_KEY"
    api_key: str | None = Field(None, description="Discouraged literal key; prefer api_key_env.")
    auth_header: str = "X-Access-Token"
    repository: str | None = None
    branch: str | None = None
    llm_model: str | None = None
    agent_profile_id: str | None = None
    agent_type: str | None = None
    plugins: list[dict[str, Any]] = Field(default_factory=list)
    confirmation_policy: Literal["risky", "always", "never"] = "risky"
    max_concurrency: int = Field(1, ge=1)
    max_cost_usd: float = Field(5.0, gt=0)
    daily_cost_limit_usd: float | None = Field(
        None, description="Optional UTC-day cost cap for this target."
    )
    max_runtime_s: int = Field(1800, gt=0)
    max_attempts: int = Field(2, ge=1)
    system_message_suffix: str | None = None
    enabled: bool = True

    @field_validator("alias")
    @classmethod
    def _alias_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("target alias must not be empty")
        return value.strip()

    @property
    def resolved_api_key(self) -> str | None:
        import os

        return os.environ.get(self.api_key_env) or self.api_key

    def confirmation(self) -> ConfirmationPolicy:
        if self.confirmation_policy == "always":
            return AlwaysConfirm()
        if self.confirmation_policy == "never":
            return NeverConfirm()
        return ConfirmRisky(threshold=SecurityRisk.MEDIUM, confirm_unknown=True)

    def public_view(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["api_key"] = None
        data["has_literal_key"] = bool(self.api_key)
        data["has_env_key"] = bool(self.resolved_api_key)
        return data


class WorkItem(BaseModel):
    """A unit of work waiting for, or under, an agent run."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    work_key: str
    source_kind: SourceKind = SourceKind.MANUAL
    source_ref: str | None = None
    title: str
    prompt: str
    target_alias: str
    repository: str | None = None
    branch: str | None = None
    priority: int = 0
    status: WorkItemStatus = WorkItemStatus.QUEUED
    attempts: int = 0
    next_attempt_at: datetime | None = None
    job_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_WORK_STATUSES

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_WORK_STATUSES

    def due(self, now: datetime) -> bool:
        return self.next_attempt_at is None or self.next_attempt_at <= now


class AgentRun(BaseModel):
    """One dispatch attempt. A work item may have several runs over time."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    work_item_id: str
    attempt: int = 1
    status: AgentRunStatus = AgentRunStatus.PENDING
    dispatch_token: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start_task_id: str | None = None
    conversation_id: str | None = None
    sandbox_id: str | None = None
    conversation_url: str | None = None
    session_api_key: str | None = None
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    policy_verified: bool = False
    cost_usd: float = 0.0
    tokens: int = 0
    summary: str | None = None
    pr_urls: list[str] = Field(default_factory=list)
    error: str | None = None
    blocked_reason: str | None = None
    cancel_requested_at: datetime | None = None
    approvals: int = 0
    rejections: int = 0
    resumes: int = 0
    signal_sent: bool = False
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_polled_at: datetime | None = None

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_RUN_STATUSES

    def public_view(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data.pop("session_api_key", None)
        return data


class ApprovalRecord(BaseModel):
    """The audit of one confirmation decision. Never stores raw secrets."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    conversation_id: str | None = None
    action_id: str
    tool_call_id: str | None = None
    tool_name: str
    risk: SecurityRisk = SecurityRisk.UNKNOWN
    decision: Decision
    rule_id: str
    reason: str
    args_digest: str
    created_at: datetime = Field(default_factory=utcnow)


class GitHubSettings(BaseModel):
    enabled: bool = False
    repos: list[str] = Field(default_factory=list)
    label: str = "odi:autopilot"
    running_label: str = "odi:running"
    done_label: str = "odi:done"
    failed_label: str = "odi:failed"
    blocked_label: str = "odi:blocked"
    token_env: str = "GITHUB_TOKEN"
    poll_interval_s: int = 60


class AutomationSettings(BaseModel):
    """OpenHands Automation adoption settings (opt-in, fail-closed).

    When enabled, the daemon discovers existing Automation conversations
    whose repo/branch match configured patterns and adopts them as tracked
    work items, never starting a second conversation for the same issue.
    """

    enabled: bool = False
    repo_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns for repos to adopt (e.g. ['acme/*', 'my-org/*']).",
    )
    label: str = "odi:automation"
    discovery_interval_s: int = Field(3600, ge=60)


class OrchestratorSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    targets: list[AgentTarget] = Field(default_factory=list)
    default_target: str | None = None
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    automation: AutomationSettings = Field(default_factory=AutomationSettings)
    workspace_root: str | None = None
    poll_interval_s: int = Field(15, ge=1)
    lease_seconds: int = Field(120, ge=30)
    max_concurrency: int | None = None
    approval_rejection_limit: int = Field(3, ge=1)
    daily_cost_limit_usd: float | None = None
    heartbeat_path: str | None = None
    schema_version: int = 1

    @field_validator("targets")
    @classmethod
    def _unique_aliases(cls, targets: list[AgentTarget]) -> list[AgentTarget]:
        seen: set[str] = set()
        for target in targets:
            if target.alias in seen:
                raise ValueError(f"duplicate target alias: {target.alias}")
            seen.add(target.alias)
        return targets

    def target(self, alias: str | None) -> AgentTarget | None:
        resolved = alias or self.default_target
        if resolved is None and len(self.targets) == 1:
            return self.targets[0]
        for target in self.targets:
            if target.alias == resolved:
                return target
        return None

    def enabled_targets(self) -> list[AgentTarget]:
        return [target for target in self.targets if target.enabled]


class OrchestratorStatus(BaseModel):
    daemon_running: bool = False
    heartbeat_at: datetime | None = None
    pid: int | None = None
    queued: int = 0
    running: int = 0
    waiting_for_confirmation: int = 0
    completed: int = 0
    failed: int = 0
    blocked: int = 0
    cancelled: int = 0
    targets: list[str] = Field(default_factory=list)
    db_path: str | None = None
    config_path: str | None = None


def serialize(value: Any) -> Any:
    """JSON-safe value for the event store."""
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value
