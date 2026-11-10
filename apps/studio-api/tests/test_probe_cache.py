"""Tests for the LLM probe TTL cache and the ``/api/health/llm`` response."""

from __future__ import annotations

import asyncio

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import probes
from agentic_odi_studio_api.studio import router as studio_router
from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(create_app(InMemoryRepository()))


def _make_healthy_probe(monkeypatch, counter):
    async def _probe(base_url, api_key, model_name):
        counter[0] += 1
        return True, "LLM backend is reachable."

    monkeypatch.setattr(probes, "_probe_llm_health", _probe)


def test_first_call_probes_second_reuses_cache(monkeypatch):
    counter = [0]
    _make_healthy_probe(monkeypatch, counter)
    t = [1000.0]

    def now() -> float:
        return t[0]

    first = asyncio.run(probes.probe_llm_health("http://probe-a/v1", "k", "m", now=now))
    assert first["cached"] is False
    assert counter[0] == 1

    second = asyncio.run(probes.probe_llm_health("http://probe-a/v1", "k", "m", now=now))
    assert second["cached"] is True
    assert counter[0] == 1  # no new upstream probe within the TTL
    assert second["checked_at"] == first["checked_at"]  # cached probe's time

    t[0] = 1031.0  # past the 30s TTL
    third = asyncio.run(probes.probe_llm_health("http://probe-a/v1", "k", "m", now=now))
    assert third["cached"] is False
    assert counter[0] == 2
    assert third["checked_at"] != first["checked_at"]


def test_fresh_bypasses_cache(monkeypatch):
    counter = [0]
    _make_healthy_probe(monkeypatch, counter)
    t = [1000.0]

    def now() -> float:
        return t[0]

    asyncio.run(probes.probe_llm_health("http://probe-b/v1", "k", "m", now=now))
    assert counter[0] == 1
    asyncio.run(probes.probe_llm_health("http://probe-b/v1", "k", "m", now=now, fresh=True))
    assert counter[0] == 2  # fresh forces a probe after a cached hit


def test_cache_retains_no_secret_or_response_body(monkeypatch):
    counter = [0]
    _make_healthy_probe(monkeypatch, counter)
    t = [1000.0]

    def now() -> float:
        return t[0]

    result = asyncio.run(probes.probe_llm_health("http://probe-c/v1", "super-secret", "m", now=now))
    assert "super-secret" not in result["message"]

    with probes._PROBE_CACHE_LOCK:
        _, stored = probes._PROBE_CACHE[("http://probe-c/v1", "m")]
    assert "super-secret" not in stored.message
    assert stored.healthy is True


def test_health_route_reports_checked_at_and_cached(monkeypatch):
    async def _fake(base_url, api_key, model_name, now=None, fresh=False):
        return {
            "healthy": True,
            "message": "LLM backend is reachable.",
            "checked_at": "2026-01-01T00:00:00+00:00",
            "cached": True,
        }

    monkeypatch.setattr(studio_router, "probe_llm_health", _fake)

    response = _client().post(
        "/api/health/llm",
        json={"base_url": "http://x/v1", "api_key": "k", "model": "m"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["healthy"] is True
    assert body["checked_at"] == "2026-01-01T00:00:00+00:00"
    assert body["cached"] is True
