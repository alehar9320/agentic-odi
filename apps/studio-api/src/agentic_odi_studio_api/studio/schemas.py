"""Pydantic request/response contracts for the Living Studio sidecar API."""

from __future__ import annotations

from typing import Literal

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


class StudioBrief(BaseModel):
    """The user's context, captured during first-run onboarding."""

    product_name: str = ""
    product_url: str = ""
    target_user: str = ""
    job_statement: str = ""
    core_problem: str = ""


class ChatRequest(BaseModel):
    base_url: str
    api_key: str = ""
    model: str
    mcp_url: str
    messages: list[ChatMessage] = Field(default_factory=list)
    brief: StudioBrief | None = None
