from __future__ import annotations

from agentic_odi_openhands import (
    ActionEvent,
    ConversationInfo,
    MessageEvent,
    ObservationEvent,
    SecurityRisk,
    StartTask,
    UserRejectObservation,
)
from agentic_odi_openhands.events import final_message, pending_actions, pr_urls
from agentic_odi_openhands.models import Event, parse_event


def test_start_task_states() -> None:
    assert StartTask(id="t", status="WAITING_FOR_SANDBOX").in_flight
    assert StartTask(id="t", status="ready").ready
    failed = StartTask(id="t", status="error", error_detail="no repo access")
    assert failed.failed
    assert failed.error_message == "no repo access"


def test_conversation_flattens_nested_payload() -> None:
    info = ConversationInfo.from_wire(
        {
            "conversation": {
                "id": "c-1",
                "execution_status": "running",
                "sandbox_status": "RUNNING",
                "blocked_actions": [{"hook": "x"}],
            },
            "sandbox_id": "sb-1",
            "conversation_url": "https://agent.test",
        }
    )
    assert info.id == "c-1"
    assert info.sandbox_id == "sb-1"
    assert info.execution is not None and info.execution.value == "running"
    assert info.has_blocked_actions


def test_security_risk_coercion() -> None:
    assert SecurityRisk.coerce("high") is SecurityRisk.HIGH
    assert SecurityRisk.coerce(None) is SecurityRisk.UNKNOWN
    # Risk carried on the nested tool call is lifted to the event.
    event = ActionEvent(tool_call={"name": "terminal", "security_risk": "HIGH"})
    assert event.security_risk is SecurityRisk.HIGH


def test_unknown_event_kind_degrades() -> None:
    event = parse_event({"id": "e-1", "kind": "SomethingNew", "source": "agent"})
    assert isinstance(event, Event)
    assert event.kind == "SomethingNew"


def test_message_and_pr_extraction() -> None:
    events = [
        MessageEvent(source="agent", llm_message={"content": [{"text": "work"}]}),
        MessageEvent(
            source="agent",
            llm_message={
                "content": [{"text": "Opened https://github.com/acme/repo/pull/12 and passed."}]
            },
        ),
        MessageEvent(source="user", llm_message={"content": [{"text": "thanks"}]}),
    ]
    text = final_message(events)
    assert text is not None and "pull/12" in text
    assert pr_urls(text) == ["https://github.com/acme/repo/pull/12"]
    assert pr_urls(None) == []


def test_pending_actions_clears_on_rejection() -> None:
    action = ActionEvent(id="e1", tool_call_id="call-1", tool_name="terminal")
    rejected = UserRejectObservation(action_id="e1", tool_call_id="call-1")
    observed = ObservationEvent(action_id="e2", tool_call_id="call-2")
    other = ActionEvent(id="e2", tool_call_id="call-2", tool_name="terminal")
    assert pending_actions([action, rejected, other, observed]) == []
