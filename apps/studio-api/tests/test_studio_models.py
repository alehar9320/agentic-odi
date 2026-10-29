"""Tests for listing the configured backend's model ids."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import probes
from agentic_odi_studio_api.studio import router as studio_router
from fastapi.testclient import TestClient


def _openai_reporting(ids: list[str], monkeypatch) -> None:
    class _Models:
        async def list(self) -> Any:
            # Shaped like the SDK's AsyncPage: items are on `.data`, and the
            # page itself is not synchronously iterable.
            return SimpleNamespace(data=[SimpleNamespace(id=model_id) for model_id in ids])

    class _FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.models = _Models()

    monkeypatch.setattr(probes, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(probes, "AsyncOpenAI", _FakeOpenAI)


def test_list_models_returns_sorted_unique_ids(monkeypatch) -> None:
    _openai_reporting(["zeta", "alpha", "alpha", ""], monkeypatch)

    models, error = asyncio.run(probes.list_models("http://llm/v1", "key"))

    assert models == ["alpha", "zeta"]
    assert error is None


def test_list_models_reports_offline_without_connecting(monkeypatch) -> None:
    monkeypatch.setattr(probes, "is_endpoint_reachable", lambda url, timeout: False)

    models, error = asyncio.run(probes.list_models("http://llm/v1", "key"))

    assert models == []
    assert error == probes.OFFLINE_MESSAGE


def test_list_models_reports_a_failed_probe_as_a_message(monkeypatch) -> None:
    class _Models:
        async def list(self) -> list[Any]:
            raise RuntimeError("connection refused")

    class _FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.models = _Models()

    monkeypatch.setattr(probes, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(probes, "AsyncOpenAI", _FakeOpenAI)

    models, error = asyncio.run(probes.list_models("http://llm/v1", "key"))

    assert models == []
    assert error == "connection_error: connection refused"


def test_models_endpoint_returns_the_list(monkeypatch) -> None:
    async def _list(base_url: str, api_key: str) -> tuple[list[str], None]:
        assert (base_url, api_key) == ("http://llm/v1", "key")
        return ["alpha", "beta"], None

    monkeypatch.setattr(studio_router, "list_models", _list)
    client = TestClient(create_app(InMemoryRepository()))

    response = client.post("/api/models", json={"base_url": "http://llm/v1", "api_key": "key"})

    assert response.status_code == 200
    assert response.json() == {"models": ["alpha", "beta"], "error": None}


def test_models_endpoint_surfaces_an_offline_backend(monkeypatch) -> None:
    async def _list(base_url: str, api_key: str) -> tuple[list[str], str]:
        return [], probes.OFFLINE_MESSAGE

    monkeypatch.setattr(studio_router, "list_models", _list)
    client = TestClient(create_app(InMemoryRepository()))

    response = client.post("/api/models", json={"base_url": "http://llm/v1"})

    assert response.status_code == 200
    assert response.json() == {"models": [], "error": probes.OFFLINE_MESSAGE}
