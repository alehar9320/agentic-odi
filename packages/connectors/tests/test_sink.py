import pytest
from agentic_odi_connectors.models import IngestBatch, IngestRecord, RateLimitExceededError
from agentic_odi_connectors.rate_limit import RateLimiter
from agentic_odi_connectors.sink import IngestSink


def test_append_stores_batch() -> None:
    sink = IngestSink()
    batch = IngestBatch(connector_name="gong")

    sink.append(batch)

    assert sink.batches() == [batch]


def test_records_flatten_batches() -> None:
    sink = IngestSink()
    first = IngestRecord(
        source_name="gong",
        source_kind="mcp",
        item_type="catalog",
        name="mcp-catalog",
        content="{}",
    )
    second = IngestRecord(
        source_name="gong",
        source_kind="mcp",
        item_type="resource",
        name="feedback",
        content="quote",
    )
    sink.append(IngestBatch(connector_name="gong", records=[first]))
    sink.append(IngestBatch(connector_name="gong", records=[second]))

    assert sink.records() == [first, second]


def test_append_refuses_a_batch_over_the_rate_limit() -> None:
    limiter = RateLimiter(rate=1, burst=1)
    sink = IngestSink(rate_limiter=limiter)
    records = [
        IngestRecord(
            source_name="gong",
            source_kind="mcp",
            item_type="resource",
            name=f"feedback-{index}",
            content="quote",
        )
        for index in range(2)
    ]

    with pytest.raises(RateLimitExceededError):
        sink.append(IngestBatch(connector_name="gong", records=records))

    assert sink.batches() == []
    assert sink.records() == []


def test_an_empty_batch_does_not_consume_tokens() -> None:
    limiter = RateLimiter(rate=1, burst=1)
    sink = IngestSink(rate_limiter=limiter)
    record = IngestRecord(
        source_name="gong",
        source_kind="mcp",
        item_type="resource",
        name="feedback",
        content="quote",
    )

    sink.append(IngestBatch(connector_name="gong"))
    sink.append(IngestBatch(connector_name="gong", records=[record]))

    assert sink.records() == [record]


def test_records_preserve_source_identity() -> None:
    sink = IngestSink()
    record = IngestRecord(
        source_name="linear",
        source_kind="mcp",
        item_type="tool_result",
        name="search",
        content="ticket",
    )
    sink.append(IngestBatch(connector_name="linear", records=[record]))

    stored = sink.records()[0]

    assert stored.source_name == "linear"
    assert stored.source_kind == "mcp"
    assert stored.name == "search"
