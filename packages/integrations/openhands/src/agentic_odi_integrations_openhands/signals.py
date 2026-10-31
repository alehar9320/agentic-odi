"""Translate terminal run states into the ODI signal inbox.

Runs that finish, fail, or block produce exactly one signal. Queued, running,
cancelled, and quiet polls produce none. The signal is the user's only
attention surface, so the title and detail state what actually happened.
"""

from __future__ import annotations

from typing import Protocol

from agentic_odi_core import SignalKind

from agentic_odi_integrations_openhands.models import (
    AgentRun,
    AgentRunStatus,
    WorkItem,
    WorkItemStatus,
)


class SignalSink(Protocol):
    def record_signal(
        self,
        kind: SignalKind,
        title: str,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        severity: str = "info",
        detail: str | None = None,
        discriminator: str = "",
    ) -> object: ...


_KIND_BY_STATUS = {
    AgentRunStatus.COMPLETED: SignalKind.AGENT_WORK_COMPLETED,
    AgentRunStatus.FAILED: SignalKind.AGENT_WORK_FAILED,
    AgentRunStatus.BLOCKED: SignalKind.AGENT_WORK_BLOCKED,
}


def _detail(run: AgentRun) -> str:
    parts: list[str] = []
    if run.summary:
        parts.append(run.summary.strip())
    if run.pr_urls:
        parts.append("PR: " + ", ".join(run.pr_urls))
    if run.cost_usd:
        parts.append(f"cost: ${run.cost_usd:.2f}")
    if run.error:
        parts.append(f"error: {run.error}")
    if run.blocked_reason:
        parts.append(f"blocked: {run.blocked_reason}")
    return " | ".join(part for part in parts if part) or "No summary was reported."


def terminal_signal(sink: SignalSink, work: WorkItem, run: AgentRun) -> object | None:
    kind = _KIND_BY_STATUS.get(run.status)
    if kind is None or run.signal_sent:
        return None
    if work.status is WorkItemStatus.CANCELLED or run.status in {
        AgentRunStatus.CANCELLED,
    }:
        return None
    severity = {
        AgentRunStatus.COMPLETED: "notice" if run.pr_urls else "info",
        AgentRunStatus.FAILED: "notice",
        AgentRunStatus.BLOCKED: "urgent",
    }[run.status]
    title = f"{work.title} [{run.status.value}]"
    discriminator = f"{run.status.value}:{run.conversation_id or run.id}"
    return sink.record_signal(
        kind,
        title[:120],
        subject_kind="agent_work",
        subject_id=run.id,
        severity=severity,
        detail=_detail(run)[:1000],
        discriminator=discriminator,
    )
