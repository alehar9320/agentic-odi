"""Pydantic request/response contracts for the Living Studio sidecar API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""


class McpHealthRequest(BaseModel):
    mcp_url: str


class LlmHealthRequest(BaseModel):
    base_url: str
    api_key: str = ""
    model: str = ""


class AddStepRequest(BaseModel):
    mcp_url: str
    job_id: str
    name: str
    order: int


class AddOutcomeRequest(BaseModel):
    mcp_url: str
    job_id: str
    statement: str
    importance: float
    satisfaction: float


class CreateJobRequest(BaseModel):
    """Create a Job by hand, with or without the model."""

    name: str = Field(min_length=1)
    description: str | None = None
    mcp_url: str = ""


class UpdateJobRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    mcp_url: str = ""


class UpdateStepRequest(BaseModel):
    name: str | None = None
    order: int | None = None
    mcp_url: str = ""


class UpdateOutcomeRequest(BaseModel):
    statement: str | None = None
    importance: float | None = None
    satisfaction: float | None = None
    mcp_url: str = ""


class V2MOM(BaseModel):
    """V2MOM framework artifact: Vision, Values, Methods, Obstacles, Measures."""

    vision: str = ""
    values: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    obstacles: list[str] = Field(default_factory=list)
    measures: list[str] = Field(default_factory=list)


class StudioBrief(BaseModel):
    """The user's context, captured during first-run onboarding."""

    product_name: str = ""
    product_url: str = ""
    target_user: str = ""
    job_statement: str = ""
    core_problem: str = ""
    v2mom: V2MOM | None = None


class UiCatalogRequest(BaseModel):
    """What the calling client can render. Omitted by non-visual clients."""

    version: int = 1
    components: list[dict[str, Any]] = Field(default_factory=list)


class ChatRequest(BaseModel):
    base_url: str
    api_key: str = ""
    model: str
    mcp_url: str
    messages: list[ChatMessage] = Field(default_factory=list)
    brief: StudioBrief | None = None
    ui_catalog: UiCatalogRequest | None = None
    conversation_id: str | None = None


class AddConnectorRequest(BaseModel):
    name: str | None = None
    preset: str | None = None
    url: str | None = None


class ConnectorListItem(BaseModel):
    name: str
    kind: str
    enabled: bool = True


class ConnectorOperationResponse(BaseModel):
    ok: bool
    name: str


ObservationKind = Literal[
    "career",
    "opportunity",
    "business",
    "stakeholder",
    "constraint",
    "evidence",
    "preference",
]
ObservationStatus = Literal["suggested", "confirmed", "dismissed"]


class ObservationModel(BaseModel):
    id: str
    kind: str
    text: str
    data: dict[str, Any] = Field(default_factory=dict)
    status: str
    confidence: float
    source_turn: int | None = None
    created_at: str
    updated_at: str


class ObservationListResponse(BaseModel):
    observations: list[ObservationModel]


class ObservationResponse(BaseModel):
    observation: ObservationModel


class ObservationCreateRequest(BaseModel):
    kind: ObservationKind
    text: str = Field(min_length=1, max_length=2000)
    data: dict[str, Any] | None = None
    confidence: float = Field(default=0.6, ge=0, le=1)
    confirmed: bool = False


class ObservationUpdateRequest(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    status: ObservationStatus | None = None
    data: dict[str, Any] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class ConversationModel(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class ConversationResponse(BaseModel):
    conversation: ConversationModel


class TurnModel(BaseModel):
    id: int
    conversation_id: str
    role: str
    content: str
    created_at: str


class LatestConversationResponse(BaseModel):
    conversation: ConversationModel | None = None
    turns: list[TurnModel] = Field(default_factory=list)
