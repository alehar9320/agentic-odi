"""The write-approval gate: it resolves once, expires, and never leaks."""

from __future__ import annotations

import asyncio
import json

import pytest
from agentic_odi_studio_api.studio.approvals import (
    ApprovalDecision,
    ApprovalNotFoundError,
    ApprovalRegistry,
    wait_for_decision,
)


def _open(registry: ApprovalRegistry) -> tuple[object, object]:
    async def _run() -> tuple[object, object]:
        return registry.open(
            tool_call_id="call-1",
            name="add_job",
            arguments={"name": "Retention"},
            prompt="Allow the assistant to add job?",
        )

    return asyncio.run(_run())


def test_open_describes_the_call_for_the_ui() -> None:
    registry = ApprovalRegistry()
    request, _future = _open(registry)

    payload = request.to_dict()  # type: ignore[attr-defined]

    assert payload["id"].startswith("apv_")
    assert payload["tool_call_id"] == "call-1"
    assert payload["name"] == "add_job"
    assert payload["arguments"] == {"name": "Retention"}
    assert payload["prompt"] == "Allow the assistant to add job?"
    assert registry.pending == 1


def test_resolve_answers_the_waiting_turn() -> None:
    registry = ApprovalRegistry()

    async def _run() -> ApprovalDecision:
        request, future = registry.open(
            tool_call_id="call-1", name="add_job", arguments={}, prompt="?"
        )
        pending = asyncio.create_task(wait_for_decision(registry, request, future, timeout=5))
        await asyncio.sleep(0)
        registry.resolve(request.id, ApprovalDecision(approved=True, reason="ok"))
        decision = await pending
        assert decision is not None
        return decision

    decision = asyncio.run(_run())

    assert decision.approved is True
    assert decision.reason == "ok"
    assert registry.pending == 0


def test_an_expired_gate_returns_none_and_is_forgotten() -> None:
    registry = ApprovalRegistry()

    async def _run() -> ApprovalDecision | None:
        request, future = registry.open(
            tool_call_id="call-1", name="add_job", arguments={}, prompt="?"
        )
        return await wait_for_decision(registry, request, future, timeout=0.01)

    assert asyncio.run(_run()) is None
    assert registry.pending == 0


def test_a_gate_answers_only_once() -> None:
    registry = ApprovalRegistry()

    async def _run() -> None:
        request, future = registry.open(
            tool_call_id="call-1", name="add_job", arguments={}, prompt="?"
        )
        registry.resolve(request.id, ApprovalDecision(approved=True))
        with pytest.raises(ApprovalNotFoundError):
            registry.resolve(request.id, ApprovalDecision(approved=False))
        await asyncio.sleep(0)
        assert future.done()

    asyncio.run(_run())


def test_an_unknown_gate_cannot_be_resolved() -> None:
    registry = ApprovalRegistry()

    with pytest.raises(ApprovalNotFoundError):
        registry.resolve("apv_missing", ApprovalDecision(approved=True))


def test_cancel_all_drops_every_pending_gate() -> None:
    registry = ApprovalRegistry()

    async def _run() -> list[bool]:
        _first, first_future = registry.open(
            tool_call_id="call-1", name="add_job", arguments={}, prompt="?"
        )
        _second, second_future = registry.open(
            tool_call_id="call-2", name="delete_job", arguments={}, prompt="?"
        )
        registry.cancel_all()
        await asyncio.sleep(0)
        return [first_future.cancelled(), second_future.cancelled()]

    assert asyncio.run(_run()) == [True, True]
    assert registry.pending == 0


def test_the_decision_serializes_for_the_stream() -> None:
    decision = ApprovalDecision(approved=False, reason="not this time")

    assert json.loads(json.dumps(decision.__dict__)) == {
        "approved": False,
        "reason": "not this time",
    }
