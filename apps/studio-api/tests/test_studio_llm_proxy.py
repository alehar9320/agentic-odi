"""Tests for the sidecar LLM chat proxy."""

from __future__ import annotations

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def test_llm_chat_proxy_returns_provider_error_for_unreachable_endpoint() -> None:
    app = create_app(repo=InMemoryRepository())
    client = TestClient(app)

    response = client.post(
        "/api/llm/chat",
        json={
            "base_url": "http://127.0.0.1:1/chat/completions",
            "api_key": "test-key",
            "model": "test-model",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: error" in body
    assert "provider_error" in body


def test_llm_chat_proxy_forwards_tools_when_provided() -> None:
    app = create_app(repo=InMemoryRepository())
    client = TestClient(app)

    response = client.post(
        "/api/llm/chat",
        json={
            "base_url": "http://127.0.0.1:1/chat/completions",
            "api_key": "test-key",
            "model": "test-model",
            "messages": [{"role": "user", "content": "hello"}],
            "tools": [{"type": "function", "function": {"name": "get_canvas"}}],
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
