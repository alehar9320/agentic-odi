"""Map connector ingest records onto ODI evidence drafts.

This module deliberately does not import the ODI store. It produces transport
records shaped for ``core.Evidence``; the CLI (or any caller) owns persistence,
so connector plumbing never leaks into the ODI repository.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from connectors.models import EvidenceItemType, IngestBatch, IngestRecord


class EvidenceDraft(BaseModel):
    """An ingest record ready to become ODI evidence."""

    source_name: str
    source_kind: str
    item_type: EvidenceItemType
    name: str
    content: str
    raw: dict[str, Any] = Field(default_factory=dict)
    job_id: str | None = None
    step_id: str | None = None
    outcome_id: str | None = None


def drafts_from_batch(
    batch: IngestBatch,
    *,
    job_id: str | None = None,
    step_id: str | None = None,
    outcome_id: str | None = None,
    include_catalog: bool = False,
) -> list[EvidenceDraft]:
    """Turn every evidence-bearing record in ``batch`` into a draft.

    Catalog records describe the connector itself and are skipped unless
    ``include_catalog`` is set.
    """
    drafts: list[EvidenceDraft] = []
    for record in batch.records:
        if record.item_type == "catalog" and not include_catalog:
            continue
        drafts.append(_draft_from_record(record, job_id, step_id, outcome_id))
    return drafts


def _draft_from_record(
    record: IngestRecord,
    job_id: str | None,
    step_id: str | None,
    outcome_id: str | None,
) -> EvidenceDraft:
    return EvidenceDraft(
        source_name=record.source_name,
        source_kind=record.source_kind,
        item_type=record.item_type,
        name=record.name,
        content=record.content,
        raw=record.raw,
        job_id=job_id,
        step_id=step_id,
        outcome_id=outcome_id,
    )
