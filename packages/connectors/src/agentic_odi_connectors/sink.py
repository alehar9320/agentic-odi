"""In-memory ingest sink owned by the connectors package."""

from __future__ import annotations

from agentic_odi_connectors.models import IngestBatch, IngestRecord


class IngestSink:
    """Stores ingested batches for the current process."""

    def __init__(self) -> None:
        self._batches: list[IngestBatch] = []

    def append(self, batch: IngestBatch) -> None:
        self._batches.append(batch)

    def batches(self) -> list[IngestBatch]:
        return list(self._batches)

    def records(self) -> list[IngestRecord]:
        return [record for batch in self._batches for record in batch.records]

    def clear(self) -> None:
        self._batches.clear()


_default_sink = IngestSink()


def get_default_sink() -> IngestSink:
    return _default_sink
