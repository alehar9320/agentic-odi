"""Pydantic request/response contracts for the Living Studio sidecar API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from agentic_odi_core import BusinessValue, CustomerValue
from agentic_odi_core.models import JobStage, V2MOM
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from agentic_odi_connectors.marketplace import MarketplaceListing


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    #: Stable id for this turn, so a branch survives a reload. Clients that do
    #: not send one are persisted in a linear chain instead.
    id: str | None = None
    parent_id: str | None = None


class McpHealthRequest(BaseModel):
    mcp_url: str


class LlmHealthRequest(BaseModel):
    base_url: str
    api_key: str = ""
    model: str = ""


class ModelListRequest(BaseModel):
    """Which backend to ask for its model ids. The key travels in the body, not
    the query string, so it never lands in a URL or an access log."""

    base_url: str
    api_key: str = ""


class AddStepRequest(BaseModel):
    mcp_url: str
    job_id: str
    name: str
    order: int
    stage: JobStage | None = None
    allow_empty_job_map: bool = False


class AddOutcomeRequest(BaseModel):
    mcp_url: str
    job_id: str
    statement: str
    importance: float = Field(ge=1.0, le=10.0)
    satisfaction: float = Field(ge=1.0, le=10.0)


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


class AddCustomerOutcomeRequest(BaseModel):
    mcp_url: str = ""
    job_id: str
    customer_value: CustomerValue
    business_value: BusinessValue
    step_id: str | None = None


class UpdateCustomerOutcomeRequest(BaseModel):
    """Both values are replaced wholesale — a partial score would be ambiguous."""

    mcp_url: str = ""
    customer_value: CustomerValue | None = None
    business_value: BusinessValue | None = None
    step_id: str | None = None


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


class AttachmentRef(BaseModel):
    """One file the user attached to a turn.

    Nothing is stored server-side: an attachment is part of the message. Text is
    extracted by the client because only the client has the file; images arrive
    as data URLs for backends that accept them.
    """

    name: str = Field(min_length=1, max_length=255)
    content_type: str = "application/octet-stream"
    size: int = Field(default=0, ge=0)
    text: str | None = Field(default=None, max_length=80_000)
    data_url: str | None = Field(default=None, max_length=8_000_000)


class ChatRequest(BaseModel):
    base_url: str
    api_key: str = ""
    model: str
    mcp_url: str
    routing_mode: str = "auto"
    messages: list[ChatMessage] = Field(default_factory=list)
    brief: StudioBrief | None = None
    ui_catalog: UiCatalogRequest | None = None
    conversation_id: str | None = None
    attachments: list[AttachmentRef] = Field(default_factory=list)
    #: Ask before a tool writes. Off by default so the CLI and older clients keep
    #: their current, unprompted behaviour.
    approvals: bool = False
    #: The id the client is streaming this reply under, so the persisted branch
    #: tree matches the one on screen.
    assistant_id: str | None = None


class ApprovalDecisionRequest(BaseModel):
    approved: bool
    reason: str = Field(default="", max_length=500)


class ApprovalDecisionResponse(BaseModel):
    ok: bool
    id: str


class AddConnectorRequest(BaseModel):
    name: str | None = None
    preset: str | None = None
    url: str | None = None
    # A marketplace listing id (`official:…` / `preset:…`) instead of a preset.
    marketplace_id: str | None = None


class ConnectorListItem(BaseModel):
    name: str
    kind: str
    enabled: bool = True


class MarketplaceListingOut(BaseModel):
    id: str
    name: str
    title: str | None = None
    summary: str = ""
    version: str = ""
    url: str | None = None
    source: str = "official"
    area: str | None = None
    repository: str | None = None
    docs: str | None = None
    env_vars: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    auth: str = "none"
    installable: bool = False
    verified: bool = False
    pull_count: int = 0
    is_recommended: bool = False
    unavailable_reason: str | None = None
    # The registry name an install produces, so the shelf can match a listing
    # against the installed list without re-deriving the slug itself.
    connector_name: str = ""

    @classmethod
    def from_listing(cls, listing: MarketplaceListing) -> MarketplaceListingOut:
        return cls(**listing.model_dump(), connector_name=listing.connector_name)


class MarketplaceSearchResponse(BaseModel):
    listings: list[MarketplaceListingOut] = Field(default_factory=list)
    areas: dict[str, str] = Field(default_factory=dict)
    cached: bool = False
    # Connection types the page can offer, with the ones not yet supported
    # listed so the UI can show them as "coming soon".
    types: list[dict[str, object]] = Field(default_factory=list)


class ConnectorOperationResponse(BaseModel):
    ok: bool
    name: str


ObservationCategory = Literal[
    "career",
    "opportunity",
    "business",
    "customer",
    "constraint",
    "decision",
    "stakeholder",
    "evidence",
    "preference",
    "other",
]
ObservationStatus = Literal["proposed", "confirmed", "dismissed"]

#: The same limit the domain entity carries: a memory note is one sentence.
MAX_OBSERVATION_TEXT = 300


class ObservationModel(BaseModel):
    id: str
    conversation_id: str | None = None
    text: str
    category: str
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
    confidence: float
    source_message_id: str | None = None
    created_at: str
    updated_at: str


class ObservationListResponse(BaseModel):
    observations: list[ObservationModel]


class ObservationResponse(BaseModel):
    observation: ObservationModel


class ObservationCreateRequest(BaseModel):
    category: ObservationCategory = "other"
    text: str = Field(min_length=1, max_length=MAX_OBSERVATION_TEXT)
    data: dict[str, Any] | None = None
    confidence: float = Field(default=0.6, ge=0, le=1)
    confirmed: bool = False
    conversation_id: str | None = None


class ObservationUpdateRequest(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=MAX_OBSERVATION_TEXT)
    status: ObservationStatus | None = None
    data: dict[str, Any] | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class ConversationModel(BaseModel):
    id: str
    title: str | None = None
    created_at: str
    updated_at: str
    head_id: str | None = None
    archived: bool = False


class ConversationResponse(BaseModel):
    conversation: ConversationModel


class ConversationListResponse(BaseModel):
    conversations: list[ConversationModel] = Field(default_factory=list)


class TurnModel(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: str
    parent_id: str | None = None
    #: The ordered surfaces the client renders, so a reload is not a plainer
    #: version of the thread it replaced.
    parts: list[dict[str, Any]] = Field(default_factory=list)


class LatestConversationResponse(BaseModel):
    conversation: ConversationModel | None = None
    turns: list[TurnModel] = Field(default_factory=list)


class TurnNode(BaseModel):
    """One turn in the branch tree, as the thread runtime needs it."""

    id: str
    parent_id: str | None = None
    role: str
    content: str
    created_at: str
    parts: list[dict[str, Any]] = Field(default_factory=list)


class ConversationTreeResponse(BaseModel):
    conversation: ConversationModel
    messages: list[TurnNode] = Field(default_factory=list)
    head_id: str | None = None


class MessageListResponse(BaseModel):
    messages: list[TurnNode] = Field(default_factory=list)


class ConversationMessagesResponse(BaseModel):
    conversation: ConversationModel
    messages: list[TurnNode] = Field(default_factory=list)


class AppendMessageRequest(BaseModel):
    """A turn the client appends itself, keyed by its own id."""

    role: Literal["user", "assistant", "tool", "system"]
    content: str = ""
    parts: list[dict[str, Any]] = Field(default_factory=list)
    id: str | None = None
    parent_id: str | None = None


class MessageResponse(BaseModel):
    message: TurnModel


class UpdateConversationRequest(BaseModel):
    head_id: str | None = None
    title: str | None = Field(default=None, max_length=200)
    archived: bool | None = None


class LlmProxyMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""


class LlmProxyRequest(BaseModel):
    base_url: str
    api_key: str = ""
    model: str
    messages: list[LlmProxyMessage] = Field(default_factory=list)
    tools: list[dict[str, Any]] | None = None
    stream: bool = True


class CapabilityItem(BaseModel):
    id: str
    label: str
    description: str
    available: bool
    reason: str | None = None


class CapabilitiesResponse(BaseModel):
    capabilities: list[CapabilityItem]


class BriefModel(BaseModel):
    """The stored brief: one per workspace, readable by the CLI and MCP too."""

    id: str = "brief"
    product_name: str = ""
    product_url: str = ""
    target_user: str = ""
    job_statement: str = ""
    core_problem: str = ""
    v2mom: V2MOM | None = None
    updated_at: str = ""


class BriefResponse(BaseModel):
    brief: BriefModel | None = None


class BriefUpdateRequest(BaseModel):
    product_name: str = ""
    product_url: str = ""
    target_user: str = ""
    job_statement: str = ""
    core_problem: str = ""
    v2mom: V2MOM | None = None


class SettingsUpdateRequest(BaseModel):
    """Model endpoint settings. The key is written here and never read back."""

    base_url: str = ""
    model: str = ""
    mcp_url: str = ""
    api_key: str | None = None


class SettingsResponse(BaseModel):
    base_url: str = ""
    model: str = ""
    mcp_url: str = ""
    has_api_key: bool = False
    masked: str = ""


class ScheduleWorkRequest(BaseModel):
    mcp_url: str = ""
    name: str
    schedule_expression: str
    agent_id: str = "default-agent"
    trigger_type: str = "oneshot"
    payload: dict[str, Any] = Field(default_factory=dict)
    job_id: str | None = None


class AddEvidenceRequest(BaseModel):
    """A research record delegated from an external tool, or captured by hand."""

    source_name: str
    source_kind: str = "manual"
    name: str
    content: str
    url: str | None = None
    item_type: Literal["catalog", "resource", "tool_result", "manual", "note"] = "manual"
    job_id: str | None = None
    step_id: str | None = None
    outcome_id: str | None = None
    mcp_url: str = ""


class PromoteEvidenceRequest(BaseModel):
    """Turn a captured record into a Job or a Desired Outcome."""

    target: Literal["job", "outcome"]
    job_id: str | None = None
    statement: str | None = None
    name: str | None = None
    importance: float | None = None
    satisfaction: float | None = None
    mcp_url: str = ""
