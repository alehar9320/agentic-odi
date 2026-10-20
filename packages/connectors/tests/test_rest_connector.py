from __future__ import annotations

import json
from typing import Any

import pytest
from agentic_odi_connectors.models import RestConnectorSettings
from agentic_odi_connectors.rest.connector import RestConnector, WebhookConnector

Calls = list[tuple[str, str, dict[str, str], bytes | None, float]]


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
