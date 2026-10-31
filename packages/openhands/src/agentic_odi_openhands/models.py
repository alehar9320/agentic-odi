"""Pydantic models for the OpenHands Cloud V1 and Agent Server wire formats.

The API is still moving, so models allow unknown fields and parsing helpers
degrade to a generic event instead of failing the whole poll. Facts the
orchestrator relies on (tool name, arguments, risk, status) are typed and
validated; everything else is preserved for diagnostics.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SecurityRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def coerce(cls, value: Any) -> SecurityRisk:
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).upper())
        except ValueError:
            return cls.UNKNOWN


class ExecutionStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    FINISHED = "finished"
    ERROR = "error"
    STUCK = "stuck"
    DELETING = "deleting"

    @classmethod
    def coerce(cls, value: Any) -> ExecutionStatus | None:
        try:
            return cls(str(value).lower())
        except ValueError:
            return None


class SandboxStatus(str, Enum):
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"
    MISSING = "MISSING"

    @classmethod
    def coerce(cls, value: Any) -> SandboxStatus | None:
        try:
            return cls(str(value).upper())
        except ValueError:
            return None


START_TASK_IN_FLIGHT = frozenset(
    {
        "working",
        "waiting_for_sandbox",
        "preparing_repository",
        "running_setup_script",
        "setting_up_git_hooks",
        "setting_up_skills",
        "starting_conversation",
    }
)
START_TASK_READY = "ready"
START_TASK_ERROR = "error"


class StartTask(BaseModel):
    """A Cloud start task: the handle returned before a sandbox is ready."""

    model_config = ConfigDict(extra="allow")

    id: str
    status: str = "working"
    app_conversation_id: str | None = None
    conversation_id: str | None = None
    error_detail: str | None = None
    detail: str | None = None

    @property
    def in_flight(self) -> bool:
        return self.status.lower() in START_TASK_IN_FLIGHT

    @property
    def ready(self) -> bool:
        return self.status.lower() == START_TASK_READY

    @property
    def failed(self) -> bool:
        return self.status.lower() == START_TASK_ERROR

    @property
    def resolved_conversation_id(self) -> str | None:
        return self.app_conversation_id or self.conversation_id

    @property
    def error_message(self) -> str:
        return self.error_detail or self.detail or f"start task ended in {self.status}"


class TextContent(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "text"
    text: str = ""


class Message(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str = "assistant"
    content: list[TextContent] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(part.text for part in self.content if part.text).strip()


class MessageToolCall(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    name: str | None = None
    arguments: str | dict[str, Any] | None = None
    function: dict[str, Any] | None = None
    security_risk: Any = None

    @property
    def tool_name(self) -> str:
        if self.name:
            return self.name
        if self.function and isinstance(self.function.get("name"), str):
            return self.function["name"]
        return ""

    @property
    def argument_dict(self) -> dict[str, Any]:
        raw: Any = self.arguments
        if raw is None and self.function is not None:
            raw = self.function.get("arguments")
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {"raw": raw}
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        return {}


class Action(BaseModel):
    """Tool arguments. Bash calls carry ``command``; editor calls ``path``."""

    model_config = ConfigDict(extra="allow")

    command: str | None = None
    path: str | None = None
    old_str: str | None = None
    new_str: str | None = None
    file_text: str | None = None
    view_range: list[int] | None = None
    thought: str | None = None

    def arguments(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class Event(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: f"event-{datetime.now(timezone.utc).timestamp()}")
    timestamp: str | None = None
    source: str = "environment"
    kind: str = "Event"


class ActionEvent(Event):
    kind: Literal["ActionEvent"] = "ActionEvent"
    thought: list[TextContent] = Field(default_factory=list)
    tool_name: str = ""
    tool_call_id: str = ""
    action: Action | None = None
    tool_call: MessageToolCall | None = None
    security_risk: SecurityRisk = SecurityRisk.UNKNOWN
    summary: str | None = None

    @property
    def arguments(self) -> dict[str, Any]:
        if self.action is not None:
            return self.action.arguments()
        if self.tool_call is not None:
            return self.tool_call.argument_dict
        return {}

    def model_post_init(self, __context: Any) -> None:
        # Accept the risk either on the event or on the nested tool call.
        if self.security_risk is SecurityRisk.UNKNOWN and self.tool_call is not None:
            self.security_risk = SecurityRisk.coerce(self.tool_call.security_risk)


class ObservationEvent(Event):
    kind: Literal["ObservationEvent"] = "ObservationEvent"
    tool_name: str = ""
    tool_call_id: str = ""
    action_id: str = ""
    observation: dict[str, Any] = Field(default_factory=dict)


class UserRejectObservation(Event):
    kind: Literal["UserRejectObservation"] = "UserRejectObservation"
    tool_name: str = ""
    tool_call_id: str = ""
    action_id: str = ""
    rejection_reason: str | None = None
    rejection_source: str | None = None


class MessageEvent(Event):
    kind: Literal["MessageEvent"] = "MessageEvent"
    llm_message: Message = Field(default_factory=Message)

    @property
    def text(self) -> str:
        return self.llm_message.text


class ConversationInfo(BaseModel):
    """Cloud app conversation and Agent Server conversation state.

    Cloud responses nest some fields, so the flattening helper accepts a
    ``conversation`` object as well as the top level.
    """

    model_config = ConfigDict(extra="allow")

    id: str = ""
    title: str | None = None
    sandbox_id: str | None = None
    conversation_url: str | None = None
    session_api_key: str | None = None
    repo: str | None = None
    branch: str | None = None
    execution_status: str | None = None
    sandbox_status: str | None = None
    blocked_actions: list[Any] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> ConversationInfo:
        data = dict(payload)
        nested = data.get("conversation")
        if isinstance(nested, dict):
            merged = {**nested, **{k: v for k, v in data.items() if k != "conversation"}}
            data = merged
        return cls.model_validate(data)

    @property
    def execution(self) -> ExecutionStatus | None:
        return ExecutionStatus.coerce(self.execution_status)

    @property
    def sandbox(self) -> SandboxStatus | None:
        return SandboxStatus.coerce(self.sandbox_status)

    @property
    def has_blocked_actions(self) -> bool:
        return bool(self.blocked_actions)


_EVENT_MODELS: dict[str, type[Event]] = {
    "ActionEvent": ActionEvent,
    "ObservationEvent": ObservationEvent,
    "UserRejectObservation": UserRejectObservation,
    "MessageEvent": MessageEvent,
}


def parse_event(payload: dict[str, Any]) -> Event:
    kind = payload.get("kind")
    model = _EVENT_MODELS.get(str(kind))
    if model is not None:
        return model.model_validate(payload)
    return Event.model_validate(payload)


class EventPage(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[Event] = Field(default_factory=list)
    next_page_id: str | None = None


# ---------------------------------------------------------------------------
# Confirmation policies
# ---------------------------------------------------------------------------


class ConfirmationPolicy(BaseModel):
    """Base class; subclasses know their own OpenHands wire shape."""

    def to_wire(self) -> dict[str, Any]:  # pragma: no cover - overridden
        raise TypeError(f"{type(self).__name__} does not implement to_wire")


class AlwaysConfirm(ConfirmationPolicy):
    kind: Literal["AlwaysConfirm"] = "AlwaysConfirm"

    def to_wire(self) -> dict[str, Any]:
        return {"kind": self.kind}


class NeverConfirm(ConfirmationPolicy):
    kind: Literal["NeverConfirm"] = "NeverConfirm"

    def to_wire(self) -> dict[str, Any]:
        return {"kind": self.kind}


class ConfirmRisky(ConfirmationPolicy):
    """Ask for anything at or above ``threshold``; unknown counts as risky."""

    kind: Literal["ConfirmRisky"] = "ConfirmRisky"
    threshold: SecurityRisk = SecurityRisk.MEDIUM
    confirm_unknown: bool = True

    def to_wire(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "threshold": self.threshold.value,
            "confirm_unknown": self.confirm_unknown,
        }
