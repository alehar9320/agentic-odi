import json

from connectors import IngestBatch, IngestRecord, IngestSink


def _batch(name: str) -> IngestBatch:
    return IngestBatch(
        connector_name=name,
        records=[
            IngestRecord(
                id="1",
                source_name=name,
                source_kind="mcp",
                item_type="catalog",
                name="catalog",
                content="{}",
                raw={},
            )
        ],
        errors=[],
    )


def test_append_accumulates_batches():
    sink = IngestSink()
    sink.append(_batch("a"))
    sink.append(_batch("b"))
    assert [b.connector_name for b in sink.batches] == ["a", "b"]


def test_records_keep_source_identity():
    sink = IngestSink()
    sink.append(_batch("gong"))
    rec = sink.batches[0].records[0]
    assert rec.source_name == "gong" and rec.source_kind == "mcp"


def test_dump_writes_json(tmp_path):
    sink = IngestSink()
    sink.append(_batch("a"))
    out = tmp_path / "dump.json"
    sink.dump(out)
    assert json.loads(out.read_text())[0]["connector_name"] == "a"
