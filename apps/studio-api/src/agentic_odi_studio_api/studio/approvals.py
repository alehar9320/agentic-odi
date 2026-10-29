"""In-process approval gates for mutating tool calls.

A mutating MCP tool (``add_job``, ``update_outcome``, …) pauses the streaming
turn until the person in front of the Studio says yes or no. The gate is a
process-local registry of pending futures: the SSE generator awaits one, and
``POST /api/approvals/{id}`` resolves it.

This is deliberately the smallest thing that is honest. The sidecar serves one
local user over one loopback socket; it has no durable job state and no worker
pool, so a gate that lives in memory is the whole requirement. Every gate has a
timeout and every gate resolves once, so a turn can never hang and a double
click can never run a tool twice.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

#: A person deciding whether the agent may write to their data deserves longer
#: than a network timeout, but the turn must still end on its own.
DEFAULT_TIMEOUT_SECONDS = 300.0


@dataclass
class ApprovalRequest:
    """One pending decision, described well enough for the UI to ask."""

    id: str
    tool_call_id: str
    name: str
    arguments: dict[str, object]
    prompt: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "arguments": self.arguments,
            "prompt": self.prompt,
            "created_at": self.created_at,
        }


@dataclass
class ApprovalDecision:
    approved: bool
    reason: str = ""


class ApprovalNotFoundError(KeyError):
    """No pending gate has that id, or it already resolved."""


class ApprovalRegistry:
    """Pending approval gates, keyed by the id the client answers with."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, asyncio.Future[ApprovalDecision]] = {}

    def open(
        self,
        *,
        tool_call_id: str,
        name: str,
        arguments: dict[str, object],
        prompt: str,
    ) -> tuple[ApprovalRequest, asyncio.Future[ApprovalDecision]]:
        """Register a gate and return its description and the future to await."""
        loop = asyncio.get_running_loop()
        request = ApprovalRequest(
            id=f"apv_{uuid.uuid4().hex[:12]}",
            tool_call_id=tool_call_id,
            name=name,
            arguments=arguments,
            prompt=prompt,
        )
        future: asyncio.Future[ApprovalDecision] = loop.create_future()
        with self._lock:
            self._pending[request.id] = future
        return request, future

    def resolve(self, approval_id: str, decision: ApprovalDecision) -> None:
        """Answer a pending gate. Raises when the gate is unknown or already closed."""
        with self._lock:
            future = self._pending.pop(approval_id, None)
        if future is None or future.done():
            raise ApprovalNotFoundError(approval_id)
        future.set_result(decision)

    def discard(self, approval_id: str) -> None:
        """Forget a gate without answering it (the turn ended first)."""
        with self._lock:
            self._pending.pop(approval_id, None)

    def cancel_all(self) -> None:
        """Drop every pending gate. Called when the sidecar shuts down."""
        with self._lock:
            pending = list(self._pending.items())
            self._pending.clear()
        for _approval_id, future in pending:
            if not future.done():
                future.cancel()

    @property
    def pending(self) -> int:
        with self._lock:
            return len(self._pending)


async def wait_for_decision(
    registry: ApprovalRegistry,
    request: ApprovalRequest,
    future: asyncio.Future[ApprovalDecision],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> ApprovalDecision | None:
    """Await a decision, returning ``None`` when the gate expired or was dropped.

    The gate is always discarded, so an expired id can never be answered later
    and a cancelled turn leaves nothing behind.
    """
    try:
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        return None
    except asyncio.CancelledError:
        raise
    finally:
        registry.discard(request.id)


__all__ = [
    "ApprovalDecision",
    "ApprovalNotFoundError",
    "ApprovalRegistry",
    "ApprovalRequest",
    "DEFAULT_TIMEOUT_SECONDS",
    "wait_for_decision",
]
