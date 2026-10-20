from connectors.mapping import drafts_from_batch
from connectors.models import IngestBatch, IngestRecord


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
