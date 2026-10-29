"""Pydantic request/response contracts for the Living Studio sidecar API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from agentic_odi_core.models import BetStatus, DecisionConfidence, JobStage, ScoreMethod
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
    importance_n: int | None = Field(None, ge=1)
    satisfaction_n: int | None = Field(None, ge=1)
    score_method: ScoreMethod = "estimate"


class RejectedOptionRequest(BaseModel):
    """One option a decision considered and turned down, with its reason."""

    outcome_id: str = Field(min_length=1)
    reason: str = ""


class RecordDecisionRequest(BaseModel):
    """Record a decision, optionally naming the one it supersedes."""

    mcp_url: str = ""
    job_id: str = Field(min_length=1)
    chosen_outcome_ids: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)
    decided_by: str = Field(min_length=1)
    decided_at: str | None = None
    rejected: list[RejectedOptionRequest] = Field(default_factory=list)
    confidence: DecisionConfidence = DecisionConfidence.MEDIUM
    supersedes: str | None = None


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
    importance_n: int | None = Field(None, ge=1)
    satisfaction_n: int | None = Field(None, ge=1)
    score_method: ScoreMethod | None = None
    at: str | None = None
    note: str | None = None
    mcp_url: str = ""


class ReviewDecisionRequest(BaseModel):
    """Re-examine a past decision against today's numbers."""

    decision_id: str = Field(min_length=1)
    today: str | None = None
    mcp_url: str = ""


class RecordBetRequest(BaseModel):
    """Record a bet: a hypothesis with its baseline captured at creation."""

    mcp_url: str = ""
    decision_id: str = Field(min_length=1)
    outcome_id: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    target: float
    measure_by: str = Field(min_length=1)
    baseline: float | None = None


class AdvanceBetRequest(BaseModel):
    """Advance a bet. The bet is named by the path, so it is not in the body."""

    status: BetStatus
    at: str | None = None
    mcp_url: str = ""


class StudioBrief(BaseModel):
    """The user's context, captured during first-run onboarding."""

    product_name: str = ""
    product_url: str = ""
    target_user: str = ""
    job_statement: str = ""
    core_problem: str = ""


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
    head_id: str | None = None


class ConversationResponse(BaseModel):
    conversation: ConversationModel


class TurnModel(BaseModel):
    id: int
    conversation_id: str
    role: str
    content: str
    created_at: str
    message_id: str | None = None
    parent_id: str | None = None


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


class ConversationTreeResponse(BaseModel):
    conversation: ConversationModel
    messages: list[TurnNode] = Field(default_factory=list)
    head_id: str | None = None


class UpdateConversationRequest(BaseModel):
    head_id: str | None = None
    title: str | None = Field(default=None, max_length=200)


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
