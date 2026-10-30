"""HTTP client for OpenHands Cloud V1 and a conversation's Agent Server.

The client is deliberately small: one method per call the orchestrator needs,
no retries of its own (the daemon owns backoff and budgets), and error
messages that never contain the key used to authenticate.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from agentic_odi_openhands.errors import (
    AuthError,
    NotFoundError,
    OpenHandsError,
    RateLimitError,
    TransientError,
    UnexpectedResponseError,
)
from agentic_odi_openhands.models import (
    ConfirmationPolicy,
    ConversationInfo,
    Event,
    EventPage,
    StartTask,
    parse_event,
)

DEFAULT_BASE_URL = "https://app.all-hands.dev"
DEFAULT_AUTH_HEADER = "X-Access-Token"
DEFAULT_TIMEOUT = 30.0

_SECRET_PATTERNS = (
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)(api[_-]?key|token|session[_-]?key)\s*[:=]\s*\S+"),
)


def _redact(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[redacted]", text)
    return text


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "results", "conversations", "start_tasks"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


class _BaseClient:
    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None,
        auth_header: str = DEFAULT_AUTH_HEADER,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._auth_header = auth_header
        self._client = client or httpx.Client(timeout=timeout, transport=transport)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> _BaseClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            if self._auth_header.lower() == "authorization":
                headers["Authorization"] = f"Bearer {self._api_key}"
            else:
                headers[self._auth_header] = self._api_key
        return headers

    def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        try:
            response = self._client.request(
                method,
                url,
                json=json,
                params=params,
                headers={**self._headers(), **(headers or {})},
            )
        except httpx.TimeoutException as exc:
            raise TransientError(f"{method} {self._path(url)} timed out") from exc
        except httpx.HTTPError as exc:
            raise TransientError(f"{method} {self._path(url)} failed: {exc}") from exc

        if response.status_code in (401, 403):
            raise AuthError(
                f"{self._path(url)} returned {response.status_code}. "
                f"Check the API key and that the configured auth header "
                f"({self._auth_header}) is the one OpenHands expects."
            )
        if response.status_code == 404:
            raise NotFoundError(f"{self._path(url)} returned 404")
        if response.status_code == 429:
            raise RateLimitError(
                f"{self._path(url)} rate limited; retry after "
                f"{response.headers.get('retry-after', 'a backoff')}"
            )
        if response.status_code >= 500:
            raise TransientError(
                f"{self._path(url)} returned {response.status_code}: {self._detail(response)}"
            )
        if response.status_code >= 400:
            raise OpenHandsError(
                f"{self._path(url)} returned {response.status_code}: {self._detail(response)}"
            )
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise UnexpectedResponseError(f"{self._path(url)} returned non-JSON content") from exc

    def _path(self, url: str) -> str:
        return url.replace(self.base_url, "") or url

    @staticmethod
    def _detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return _redact(response.text[:300])
        if isinstance(payload, dict):
            for key in ("detail", "message", "error"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return _redact(value[:300])
        return _redact(str(payload)[:300])


class OpenHandsClient(_BaseClient):
    """Cloud V1 client. ``base_url`` is the deployment root, not ``/api/v1``."""

    def _v1(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"

    # -- startup ---------------------------------------------------------

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
    ) -> StartTask:
        body: dict[str, Any] = {
            "initial_message": initial_message,
            "trigger": "openhands_api",
        }
        optional = {
            "selected_repository": repository,
            "selected_branch": branch,
            "llm_model": llm_model,
            "agent_profile_id": agent_profile_id,
            "agent_type": agent_type,
            "plugins": plugins,
            "title": title,
            "system_message_suffix": system_message_suffix,
            "observability_metadata": observability_metadata,
            "observability_tags": observability_tags,
        }
        for key, value in optional.items():
            if value is not None:
                body[key] = value
        payload = self._request("POST", self._v1("/app-conversations"), json=body)
        if not isinstance(payload, dict):
            raise UnexpectedResponseError("start conversation did not return an object")
        if "id" not in payload:
            raise UnexpectedResponseError("start conversation response has no start-task id")
        return StartTask.model_validate(payload)

    def get_start_tasks(self, ids: list[str]) -> list[StartTask]:
        if not ids:
            return []
        payload = self._request(
            "GET",
            self._v1("/app-conversations/start-tasks"),
            params={"ids": ids},
        )
        return [StartTask.model_validate(item) for item in _items(payload)]

    def get_start_task(self, task_id: str) -> StartTask | None:
        tasks = self.get_start_tasks([task_id])
        for task in tasks:
            if task.id == task_id:
                return task
        return tasks[0] if tasks else None

    # -- conversations ---------------------------------------------------

    def get_conversation(self, conversation_id: str) -> ConversationInfo:
        payload = self._request("GET", self._v1(f"/app-conversations/{conversation_id}"))
        if not isinstance(payload, dict):
            raise UnexpectedResponseError("conversation response is not an object")
        return ConversationInfo.from_wire(payload)

    def search_conversations(self, title_contains: str) -> list[ConversationInfo]:
        payload = self._request(
            "GET",
            self._v1("/app-conversations"),
            params={"title__contains": title_contains},
        )
        return [ConversationInfo.from_wire(item) for item in _items(payload)]

    def delete_conversation(self, conversation_id: str) -> None:
        self._request("DELETE", self._v1(f"/app-conversations/{conversation_id}"))

    def search_events(
        self,
        conversation_id: str,
        *,
        page_id: str | None = None,
        limit: int = 100,
    ) -> EventPage:
        params: dict[str, Any] = {"limit": limit}
        if page_id:
            params["page_id"] = page_id
        payload = self._request(
            "GET",
            self._v1(f"/conversation/{conversation_id}/events/search"),
            params=params,
        )
        return _event_page(payload)

    def send_message(self, conversation_id: str, message: str) -> None:
        self._request(
            "POST",
            self._v1(f"/app-conversations/{conversation_id}/send-message"),
            json={"message": message},
        )

    # -- sandboxes -------------------------------------------------------

    def resume_sandbox(self, sandbox_id: str) -> None:
        self._request("POST", self._v1(f"/sandboxes/{sandbox_id}/resume"))

    def pause_sandbox(self, sandbox_id: str) -> None:
        self._request("POST", self._v1(f"/sandboxes/{sandbox_id}/pause"))

    def delete_sandbox(self, sandbox_id: str) -> None:
        self._request("DELETE", self._v1(f"/sandboxes/{sandbox_id}"))


OpenHandsCloudClient = OpenHandsClient


def _event_page(payload: Any) -> EventPage:
    if not isinstance(payload, dict):
        raise UnexpectedResponseError("event search response is not an object")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raw_items = []
    return EventPage(
        items=[parse_event(item) for item in raw_items if isinstance(item, dict)],
        next_page_id=payload.get("next_page_id"),
    )


class AgentServerClient(_BaseClient):
    """Client for the per-conversation Agent Server.

    Authenticates with the conversation's ``session_api_key``. The key is held
    only in memory and is never included in an error message.
    """

    def __init__(
        self,
        conversation_url: str,
        session_api_key: str | None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            conversation_url,
            api_key=session_api_key,
            auth_header="X-Session-API-Key",
            timeout=timeout,
            transport=transport,
            client=client,
        )

    def _api(self, path: str) -> str:
        return f"{self.base_url}/api{path}"

    def get_conversation(self, conversation_id: str) -> ConversationInfo:
        payload = self._request("GET", self._api(f"/conversations/{conversation_id}"))
        if not isinstance(payload, dict):
            raise UnexpectedResponseError("agent conversation response is not an object")
        return ConversationInfo.from_wire(payload)

    def search_events(
        self,
        conversation_id: str,
        *,
        page_id: str | None = None,
        limit: int = 100,
    ) -> EventPage:
        params: dict[str, Any] = {"limit": limit}
        if page_id:
            params["page_id"] = page_id
        payload = self._request(
            "GET",
            self._api(f"/conversations/{conversation_id}/events/search"),
            params=params,
        )
        return _event_page(payload)

    def set_confirmation_policy(self, conversation_id: str, policy: ConfirmationPolicy) -> None:
        self._request(
            "POST",
            self._api(f"/conversations/{conversation_id}/confirmation_policy"),
            json=policy.to_wire(),
        )

    def respond_to_confirmation(
        self, conversation_id: str, action_id: str, accept: bool, reason: str | None = None
    ) -> None:
        body: dict[str, Any] = {"accept": accept}
        if reason:
            body["reason"] = reason
        self._request(
            "POST",
            self._api(f"/conversations/{conversation_id}/events/respond_to_confirmation"),
            params={"action_id": action_id},
            json=body,
        )

    def pause_conversation(self, conversation_id: str) -> None:
        self._request("POST", self._api(f"/conversations/{conversation_id}/pause"))

    def delete_conversation(self, conversation_id: str) -> None:
        self._request("DELETE", self._api(f"/conversations/{conversation_id}"))


def event_kinds(events: list[Event]) -> list[str]:
    """Small diagnostic helper used by tests and adapters."""
    return [event.kind for event in events]
