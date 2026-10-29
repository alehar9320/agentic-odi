from agentic_odi_connectors.mapping import drafts_from_batch
from agentic_odi_connectors.models import IngestBatch, IngestRecord


def _batch() -> IngestBatch:
    return IngestBatch(
        connector_name="gong",
        records=[
            IngestRecord(
                source_name="gong",
                source_kind="mcp",
                item_type="catalog",
                name="mcp-catalog",
                content="{}",
            ),
            IngestRecord(
                source_name="gong",
                source_kind="mcp",
                item_type="resource",
                name="feedback",
                content="Onboarding is slow",
                raw={"uri": "resource://feedback"},
            ),
            IngestRecord(
                source_name="gong",
                source_kind="mcp",
                item_type="tool_result",
                name="latest_quote",
                content="Lost two hours",
            ),
        ],
    )


def test_mapping_skips_catalog_by_default() -> None:
    drafts = drafts_from_batch(_batch())

    assert [draft.name for draft in drafts] == ["feedback", "latest_quote"]
    assert all(draft.source_name == "gong" for draft in drafts)
    assert drafts[0].raw == {"uri": "resource://feedback"}


def test_mapping_can_include_catalog() -> None:
    drafts = drafts_from_batch(_batch(), include_catalog=True)

    assert [draft.name for draft in drafts] == ["mcp-catalog", "feedback", "latest_quote"]


def test_mapping_attaches_odi_links() -> None:
    drafts = drafts_from_batch(_batch(), job_id="j1", step_id="s1", outcome_id="o1")

    assert all(draft.job_id == "j1" for draft in drafts)
    assert all(draft.step_id == "s1" for draft in drafts)
    assert all(draft.outcome_id == "o1" for draft in drafts)


def test_a_draft_has_exactly_the_evidence_contract_fields() -> None:
    drafts = drafts_from_batch(_batch())
    draft = drafts[0]

    assert draft.model_dump() == {
        "source_name": "gong",
        "source_kind": "mcp",
        "item_type": "resource",
        "name": "feedback",
        "content": "Onboarding is slow",
        "url": "resource://feedback",
        "raw": {"uri": "resource://feedback"},
        "job_id": None,
        "step_id": None,
        "outcome_id": None,
    }
    # The ODI store owns ids; a draft must not invent one.
    assert "id" not in draft.model_dump()


def test_unknown_payload_keys_stay_inside_raw() -> None:
    batch = IngestBatch(
        connector_name="gong",
        records=[
            IngestRecord(
                source_name="gong",
                source_kind="rest",
                item_type="resource",
                name="feedback",
                content="Onboarding is slow",
                raw={"vendor_field": "x", "nested": {"score": 3}},
            )
        ],
    )

    draft = drafts_from_batch(batch)[0]

    assert draft.raw == {"vendor_field": "x", "nested": {"score": 3}}
    assert not hasattr(draft, "vendor_field")
    assert set(draft.model_dump()) == {
        "source_name",
        "source_kind",
        "item_type",
        "name",
        "content",
        "url",
        "raw",
        "job_id",
        "step_id",
        "outcome_id",
    }


def test_mapping_preserves_record_order_and_count() -> None:
    drafts = drafts_from_batch(_batch(), include_catalog=True)

    assert len(drafts) == len(_batch().records)
    assert [draft.item_type for draft in drafts] == ["catalog", "resource", "tool_result"]
