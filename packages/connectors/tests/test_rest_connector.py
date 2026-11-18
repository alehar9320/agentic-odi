from __future__ import annotations

import json
import time
from typing import Any

import pytest
from agentic_odi_connectors.models import (
    HealthStatus,
    IngestBatch,
    RestConnectorSettings,
)
from agentic_odi_connectors.protocol import Connector
from agentic_odi_connectors.rest.connector import (
    RestConnector,
    WebhookConnector,
    clear_health_cache,
)

Calls = list[tuple[str, str, dict[str, str], bytes | None, float]]


def test_package_exports_all_public_names() -> None:
    import agentic_odi_connectors as connectors

    expected = {
        "DEFAULT_INGEST_RATE",
        "KNOWN_KINDS",
        "LinkPreviewData",
        "REQUIRED_KEYS",
        "clear_health_cache",
        "validate_connector_config",
    }

    assert expected <= set(connectors.__all__)
    assert [name for name in connectors.__all__ if not hasattr(connectors, name)] == []


@pytest.fixture(autouse=True)
def _isolated_health_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTIC_ODI_CONNECTORS_CACHE", str(tmp_path / "connector-health.json"))


def _fetcher(status: int, payload: Any, calls: Calls | None = None):
    def fetch(
        method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float
    ) -> tuple[int, bytes]:
        if calls is not None:
            calls.append((method, url, headers, body, timeout))
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return status, text.encode("utf-8")

    return fetch


def _connector(payload: Any, status: int = 200, **settings: Any) -> RestConnector:
    base: dict[str, Any] = {"url": "https://api.example/records"}
    base.update(settings)
    return RestConnector(
        name="jira",
        settings=RestConnectorSettings(**base),
        fetcher=_fetcher(status, payload),
    )


@pytest.mark.asyncio
async def test_health_reports_reachable_on_2xx() -> None:
    status = await _connector([]).health()

    assert status.ok is True
    assert status.message == "reachable"
    assert status.details["status"] == 200


@pytest.mark.asyncio
async def test_health_reports_http_failure() -> None:
    status = await _connector([], status=503).health()

    assert status.ok is False
    assert "503" in status.message


@pytest.mark.asyncio
async def test_health_reuses_a_result_checked_moments_ago() -> None:
    calls: Calls = []
    connector = RestConnector(
        name="jira",
        settings=RestConnectorSettings(url="https://api.example/records"),
        fetcher=_fetcher(200, [], calls),
    )

    first = await connector.health()
    second = await connector.health()

    assert len(calls) == 1
    assert "cached" not in first.details
    assert second.details["cached"] is True


@pytest.mark.asyncio
async def test_health_refetches_once_the_cache_expires(monkeypatch) -> None:
    calls: Calls = []
    connector = RestConnector(
        name="jira",
        settings=RestConnectorSettings(url="https://api.example/records"),
        fetcher=_fetcher(200, [], calls),
    )
    await connector.health()

    now = time.time()
    monkeypatch.setattr("agentic_odi_connectors.rest.connector.time.time", lambda: now + 31)
    await connector.health()

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_clear_health_cache_forces_a_fresh_check() -> None:
    calls: Calls = []
    connector = RestConnector(
        name="jira",
        settings=RestConnectorSettings(url="https://api.example/records"),
        fetcher=_fetcher(200, [], calls),
    )
    await connector.health()

    clear_health_cache("jira")
    await connector.health()

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_ingest_normalizes_list_payload() -> None:
    batch = await _connector([{"name": "ticket-1", "content": "Login fails"}]).ingest()

    assert batch.errors == []
    assert len(batch.records) == 1
    record = batch.records[0]
    assert record.name == "ticket-1"
    assert record.content == "Login fails"
    assert record.source_name == "jira"
    assert record.source_kind == "rest"


@pytest.mark.asyncio
async def test_ingest_follows_the_next_page_until_exhausted() -> None:
    pages = {
        "https://api.example/records": {
            "records": [{"name": "one", "content": "first"}],
            "next": "/records?page=2",
        },
        "https://api.example/records?page=2": {
            "records": [{"name": "two", "content": "second"}],
            "next": None,
        },
    }
    calls: list[str] = []

    def fetch(method, url, headers, body, timeout):
        calls.append(url)
        return 200, json.dumps(pages[url]).encode("utf-8")

    connector = RestConnector(
        name="jira",
        settings=RestConnectorSettings(
            url="https://api.example/records",
            pagination={"next_path": "next"},
        ),
        fetcher=fetch,
    )

    batch = await connector.ingest()

    assert [record.name for record in batch.records] == ["one", "two"]
    assert calls == [
        "https://api.example/records",
        "https://api.example/records?page=2",
    ]


@pytest.mark.asyncio
async def test_ingest_stops_at_one_page_without_pagination_opt_in() -> None:
    batch = await _connector(
        {
            "records": [{"name": "one", "content": "first"}],
            "next": "/records?page=2",
        }
    ).ingest()

    assert [record.name for record in batch.records] == ["one"]


@pytest.mark.asyncio
async def test_ingest_uses_records_key_and_serializes_objects() -> None:
    payload = {"result": {"issues": [{"id": "ABC-1", "summary": "Slow deploy"}]}}
    batch = await _connector(payload, records_key="result.issues").ingest()

    assert len(batch.records) == 1
    assert batch.records[0].name == "ABC-1"
    assert batch.records[0].content == "Slow deploy"
    assert batch.records[0].raw["id"] == "ABC-1"


@pytest.mark.asyncio
async def test_ingest_treats_plain_text_as_one_record() -> None:
    batch = await _connector("customer says onboarding is slow").ingest()

    assert len(batch.records) == 1
    assert batch.records[0].content == "customer says onboarding is slow"


@pytest.mark.asyncio
async def test_ingest_records_fetch_errors() -> None:
    def fetch(*_args: Any) -> tuple[int, bytes]:
        raise ConnectionError("refused")

    connector = RestConnector(
        name="jira",
        settings=RestConnectorSettings(url="https://api.example/records"),
        fetcher=fetch,
    )

    batch = await connector.ingest()

    assert batch.records == []
    assert "refused" in batch.errors[0]


@pytest.mark.asyncio
async def test_preview_returns_link_preview_data() -> None:
    connector = RestConnector(
        name="jira",
        settings=RestConnectorSettings(url="https://api.example/items"),
        fetcher=_fetcher(200, {"title": "Ticket", "status": "Open", "url": "https://ex/1"}),
    )

    preview = await connector.preview("1")

    assert preview is not None
    assert preview.title == "Ticket"
    assert preview.status == "Open"
    assert preview.url == "https://ex/1"
    assert preview.fetched_at is not None


@pytest.mark.asyncio
async def test_preview_returns_none_on_404() -> None:
    connector = RestConnector(
        name="jira",
        settings=RestConnectorSettings(url="https://api.example/items"),
        fetcher=_fetcher(404, {"error": "not found"}),
    )

    preview = await connector.preview("missing")

    assert preview is None


@pytest.mark.asyncio
async def test_preview_appends_encoded_id_to_path_and_preserves_query() -> None:
    calls: Calls = []
    connector = RestConnector(
        name="jira",
        settings=RestConnectorSettings(url="https://api.example/items?limit=50"),
        fetcher=_fetcher(200, {"title": "Ticket"}, calls),
    )

    preview = await connector.preview("a#b")

    assert preview is not None
    assert calls[0][1] == "https://api.example/items/a%23b?limit=50"


@pytest.mark.asyncio
async def test_webhook_posts_json_body_and_uses_configured_item_type() -> None:
    calls: Calls = []
    connector = WebhookConnector(
        name="inbox",
        settings=RestConnectorSettings(
            url="https://hooks.example/inbox",
            method="POST",
            json_body={"query": "latest"},
            item_type="tool_result",
        ),
        fetcher=_fetcher(200, {"records": [{"name": "quote", "content": "Too slow"}]}, calls),
    )

    batch = await connector.ingest()

    method, url, headers, body, _timeout = calls[0]
    assert (method, url) == ("POST", "https://hooks.example/inbox")
    assert headers["Content-Type"] == "application/json"
    assert body is not None and json.loads(body) == {"query": "latest"}
    assert batch.records[0].source_kind == "webhook"
    assert batch.records[0].item_type == "tool_result"


@pytest.mark.asyncio
async def test_preview_maps_a_supported_item() -> None:
    calls: Calls = []
    connector = RestConnector(
        name="jira",
        settings=RestConnectorSettings(url="https://api.example/records"),
        fetcher=_fetcher(
            200,
            {
                "title": "Slow corn germination",
                "status": "In Progress",
                "html_url": "https://jira.example/ODI-42",
            },
            calls,
        ),
    )

    preview = await connector.preview("ODI-42")

    assert preview is not None
    assert preview.title == "Slow corn germination"
    assert preview.status == "In Progress"
    assert preview.url == "https://jira.example/ODI-42"
    assert preview.fetched_at is not None
    assert len(calls) == 1
    assert calls[0][1] == "https://api.example/records/ODI-42"


@pytest.mark.asyncio
async def test_preview_accepts_a_full_url_as_the_external_id() -> None:
    calls: Calls = []
    connector = RestConnector(
        name="jira",
        settings=RestConnectorSettings(url="https://api.example/records"),
        fetcher=_fetcher(200, {"name": "Quote"}, calls),
    )

    preview = await connector.preview("https://api.example/records/ODI-9")

    assert preview is not None
    assert preview.title == "Quote"
    assert calls[0][1] == "https://api.example/records/ODI-9"


@pytest.mark.asyncio
async def test_preview_returns_none_on_http_404() -> None:
    connector = _connector({"error": "not found"}, status=404)

    assert await connector.preview("ODI-404") is None


@pytest.mark.asyncio
async def test_preview_returns_none_on_http_3xx() -> None:
    connector = _connector({"title": "Moved"}, status=301)

    assert await connector.preview("ODI-301") is None


@pytest.mark.asyncio
async def test_preview_returns_none_on_a_non_object_body() -> None:
    connector = _connector(["not", "an", "object"], status=200)

    assert await connector.preview("ODI-1") is None


@pytest.mark.asyncio
async def test_preview_returns_none_when_the_fetcher_raises() -> None:
    def fetch(*_args: Any) -> tuple[int, bytes]:
        raise ConnectionError("refused")

    connector = RestConnector(
        name="jira",
        settings=RestConnectorSettings(url="https://api.example/records"),
        fetcher=fetch,
    )

    assert await connector.preview("ODI-1") is None


@pytest.mark.asyncio
async def test_preview_defaults_to_none_when_not_overridden() -> None:
    class PlainConnector(Connector):
        kind = "plain"
        name = "plain"

        async def health(self) -> HealthStatus:
            return HealthStatus(ok=True, message="ok")

        async def ingest(self) -> IngestBatch:
            return IngestBatch(connector_name=self.name)

    connector = PlainConnector()

    assert await connector.preview("anything") is None
