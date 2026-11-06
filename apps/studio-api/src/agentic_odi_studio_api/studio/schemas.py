from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BriefingItemOut(BaseModel):
    kind: str
    text: str
    record_id: str
    record_kind: str


class BriefingOut(BaseModel):
    run_id: str
    created_at: str | Any = None
    items: list[BriefingItemOut] = Field(default_factory=list)
