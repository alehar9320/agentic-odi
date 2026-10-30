from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from agentic_odi_openhands import (
    AgentServerClient,
    AuthError,
    ConfirmRisky,
    NotFoundError,
    OpenHandsClient,
    OpenHandsError,
    RateLimitError,
    SecurityRisk,
    TransientError,
    UnexpectedResponseError,
    pending_actions,
)


def _client(handler, **kwargs: Any) -> OpenHandsClient:
    return OpenHandsClient(
        "https://cloud.test", api_key="test-key", transport=httpx.MockTransport(handler), **kwargs
    )


def _json(payload: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


def test_default_auth_header_and_start_body() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["request"] = request
        seen["body"] = json.loads(request.content)
        return _json({"id": "task-1", "status": "working"})

    task = _client(handler).start_conversation(
        "Do the thing",
        repository="acme/repo",
        branch="odi/work-1",
        title="[odi:w1] Do the thing",
        observability_metadata={"odi_work_id": "w1"},
        observability_tags=["odi", "autopilot"],
    )

    request = seen["request"]
    assert request.method == "POST"
    assert request.url.path == "/api/v1/app-conversations"
    assert request.headers["X-Access-Token"] == "test-key"
    assert seen["body"] == {
        "initial_message": "Do the thing",
        "trigger": "openhands_api",
        "selected_repository": "acme/repo",
        "selected_branch": "odi/work-1",
        "title": "[odi:w1] Do the thing",
        "observability_metadata": {"odi_work_id": "w1"},
        "observability_tags": ["odi", "autopilot"],
    }
    assert task.id == "task-1"
    assert task.in_flight


def test_authorization_bearer_variant() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        return _json({"id": "task-1"})

    client = OpenHandsClient(
        "https://cloud.test",
        api_key="test-key",
        auth_header="Authorization",
        transport=httpx.MockTransport(handler),
    )
    client.start_conversation("hello")
    assert seen["headers"]["Authorization"] == "Bearer test-key"
    assert "X-Access-Token" not in seen["headers"]


@pytest.mark.parametrize(
    "status,error",
    [
        (401, AuthError),
        (403, AuthError),
        (404, NotFoundError),
        (429, RateLimitError),
        (500, TransientError),
        (503, TransientError),
        (422, OpenHandsError),
    ],
)
def test_status_mapping(status: int, error: type[Exception]) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return _json({"detail": "nope"}, status=status)

    with pytest.raises(error):
        _client(handler).get_conversation("c-1")


def test_auth_error_names_the_header_without_leaking_the_key() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return _json({"detail": "bad token=super-secret"}, status=401)

    with pytest.raises(AuthError) as excinfo:
        _client(handler).get_conversation("c-1")
    message = str(excinfo.value)
    assert "X-Access-Token" in message
    assert "super-secret" not in message


def test_error_body_is_redacted() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return _json({"detail": "bad api_key=super-secret"}, status=400)

    with pytest.raises(OpenHandsError) as excinfo:
        _client(handler).get_conversation("c-1")
    assert "super-secret" not in str(excinfo.value)
    assert "[redacted]" in str(excinfo.value)


def test_non_json_success_is_unexpected() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>")

    with pytest.raises(UnexpectedResponseError):
        _client(handler).get_conversation("c-1")


def test_start_tasks_and_conversation_search_parameters() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "start-tasks" in request.url.path:
            return _json(
                {"items": [{"id": "task-1", "status": "ready", "app_conversation_id": "conv-1"}]}
            )
        return _json({"items": [{"id": "conv-1", "title": "[odi:w1]"}]})

    client = _client(handler)
    task = client.get_start_task("task-1")
    assert task is not None and task.ready
    assert task.resolved_conversation_id == "conv-1"

    conversations = client.search_conversations("[odi:w1]")
    assert [c.id for c in conversations] == ["conv-1"]
    assert seen[0].url.params.get_list("ids") == ["task-1"]
    assert seen[1].url.params["title__contains"] == "[odi:w1]"


def test_event_page_parses_action_observation_and_pending() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return _json(
            {
                "items": [
                    {
                        "id": "e1",
                        "kind": "ActionEvent",
                        "source": "agent",
                        "tool_name": "terminal",
                        "tool_call_id": "call-1",
                        "action": {"command": "pytest -q"},
                        "security_risk": "LOW",
                    },
                    {
                        "id": "e2",
                        "kind": "ActionEvent",
                        "source": "agent",
                        "tool_name": "terminal",
                        "tool_call_id": "call-2",
                        "action": {"command": "git status"},
                        "security_risk": "LOW",
                    },
                    {
                        "id": "e3",
                        "kind": "ObservationEvent",
                        "source": "environment",
                        "tool_call_id": "call-1",
                        "action_id": "e1",
                    },
                    {
                        "id": "e4",
                        "kind": "MessageEvent",
                        "source": "agent",
                        "llm_message": {"role": "assistant", "content": [{"text": "done"}]},
                    },
                ],
                "next_page_id": "page-2",
            }
        )

    page = _client(handler).search_events("c-1", limit=10)
    assert page.next_page_id == "page-2"
    assert [event.kind for event in page.items] == [
        "ActionEvent",
        "ActionEvent",
        "ObservationEvent",
        "MessageEvent",
    ]
    actions = pending_actions(page.items)
    assert [action.tool_call_id for action in actions] == ["call-2"]
    assert actions[0].arguments == {"command": "git status"}


def test_agent_server_policy_and_confirmation_shapes() -> None:
    seen: list[tuple[httpx.Request, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        seen.append((request, body))
        return httpx.Response(200, json={})

    client = AgentServerClient(
        "https://agent.test", "session-key", transport=httpx.MockTransport(handler)
    )
    client.set_confirmation_policy(
        "c-1", ConfirmRisky(threshold=SecurityRisk.MEDIUM, confirm_unknown=True)
    )
    client.respond_to_confirmation("c-1", "action-7", accept=False, reason="outside repo")

    policy_request, policy_body = seen[0]
    assert policy_request.url.path == "/api/conversations/c-1/confirmation_policy"
    assert policy_body == {
        "kind": "ConfirmRisky",
        "threshold": "MEDIUM",
        "confirm_unknown": True,
    }
    assert policy_request.headers["X-Session-API-Key"] == "session-key"

    confirm_request, confirm_body = seen[1]
    assert confirm_request.url.path == ("/api/conversations/c-1/events/respond_to_confirmation")
    assert confirm_request.url.params["action_id"] == "action-7"
    assert confirm_body == {"accept": False, "reason": "outside repo"}


def test_sandbox_and_conversation_lifecycle_paths() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return httpx.Response(200, json={})

    client = _client(handler)
    client.resume_sandbox("sb-1")
    client.pause_sandbox("sb-1")
    client.delete_sandbox("sb-1")
    client.send_message("c-1", "please continue")
    client.delete_conversation("c-1")

    assert seen == [
        ("POST", "/api/v1/sandboxes/sb-1/resume"),
        ("POST", "/api/v1/sandboxes/sb-1/pause"),
        ("DELETE", "/api/v1/sandboxes/sb-1"),
        ("POST", "/api/v1/app-conversations/c-1/send-message"),
        ("DELETE", "/api/v1/app-conversations/c-1"),
    ]


def test_network_failure_is_transient() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(TransientError, match="failed"):
        _client(handler).get_conversation("c-1")
