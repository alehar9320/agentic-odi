"""In-memory ingest sink for accumulating connector batches."""

from __future__ import annotations

import json
from pathlib import Path

from .models import IngestBatch


class IngestSink:
    """Collects ingest batches in memory and can dump them to JSON."""

    def __init__(self) -> None:
        self._batches: list[IngestBatch] = []

    def append(self, batch: IngestBatch) -> None:
        self._batches.append(batch)

    @property
    def batches(self) -> list[IngestBatch]:
        return list(self._batches)

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps([batch.model_dump() for batch in self._batches]))
