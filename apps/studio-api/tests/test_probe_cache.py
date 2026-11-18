"""Tests for the LLM probe TTL cache and the ``/api/health/llm`` response."""

from __future__ import annotations

import asyncio
import hashlib

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

    key_hash = hashlib.sha256("super-secret".encode()).hexdigest()[:16]
    with probes._PROBE_CACHE_LOCK:
        _, stored = probes._PROBE_CACHE[("http://probe-c/v1", "m", key_hash)]
    assert "super-secret" not in stored.message
    assert stored.healthy is True


def test_a_new_credential_does_not_reuse_the_old_verdict(monkeypatch):
    """Changing the API key must not reuse a cached verdict for the old key."""
    counter = [0]

    async def _probe(base_url, api_key, model_name):
        counter[0] += 1
        # First call (key A) fails, second call (key B) succeeds
        if api_key == "key-A":
            return False, "connection_error: invalid key"
        return True, "LLM backend is reachable."

    monkeypatch.setattr(probes, "_probe_llm_health", _probe)
    t = [1000.0]

    def now() -> float:
        return t[0]

    # Prime cache with failing probe for key A
    first = asyncio.run(probes.probe_llm_health("http://probe/v1", "key-A", "model", now=now))
    assert first["healthy"] is False
    assert counter[0] == 1

    # Change to key B - should NOT reuse the cached failure
    second = asyncio.run(probes.probe_llm_health("http://probe/v1", "key-B", "model", now=now))
    assert second["healthy"] is True
    assert second["cached"] is False
    assert counter[0] == 2  # new probe was actually called


def test_invalidate_probe_cache_drops_every_entry(monkeypatch):
    """Calling invalidate_probe_cache must clear the entire cache."""
    counter = [0]
    _make_healthy_probe(monkeypatch, counter)
    t = [1000.0]

    def now() -> float:
        return t[0]

    # Clear any existing cache entries from other tests
    with probes._PROBE_CACHE_LOCK:
        probes._PROBE_CACHE.clear()

    # Prime two different cache entries
    asyncio.run(probes.probe_llm_health("http://probe-1/v1", "k", "m1", now=now))
    asyncio.run(probes.probe_llm_health("http://probe-2/v1", "k", "m2", now=now))
    assert counter[0] == 2

    with probes._PROBE_CACHE_LOCK:
        assert len(probes._PROBE_CACHE) == 2

    # Invalidate the cache
    probes.invalidate_probe_cache()

    with probes._PROBE_CACHE_LOCK:
        assert len(probes._PROBE_CACHE) == 0

    # Next call should probe again
    asyncio.run(probes.probe_llm_health("http://probe-1/v1", "k", "m1", now=now))
    assert counter[0] == 3


def test_a_cached_verdict_is_still_reused_within_the_ttl(monkeypatch):
    """Unchanged behaviour guard: cache hits work within TTL when nothing changed."""
    counter = [0]
    _make_healthy_probe(monkeypatch, counter)
    t = [1000.0]

    def now() -> float:
        return t[0]

    # First call populates cache
    first = asyncio.run(probes.probe_llm_health("http://probe/v1", "k", "m", now=now))
    assert first["cached"] is False
    assert counter[0] == 1

    # Multiple calls within TTL should reuse cache
    for _ in range(5):
        result = asyncio.run(probes.probe_llm_health("http://probe/v1", "k", "m", now=now))
        assert result["cached"] is True
        assert result["checked_at"] == first["checked_at"]

    assert counter[0] == 1  # no additional probes


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
