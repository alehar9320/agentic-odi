"""Tests for endpoint probing and LLM health classification."""

from __future__ import annotations

import asyncio
from typing import Any

from agentic_odi_studio_api.studio import probes


def test_is_endpoint_reachable_is_false_for_an_unresolvable_endpoint() -> None:
    assert probes.is_endpoint_reachable("http://127.0.0.1:1/mcp", timeout=0.05) is False


def test_is_endpoint_reachable_defaults_the_port_from_the_scheme(monkeypatch) -> None:
    seen: list[tuple[str, int]] = []

    class _Connection:
        def __enter__(self):
            return self

        def __exit__(self, *exc: Any) -> None:
            return None

    def _create_connection(address, timeout):
        seen.append(address)
        return _Connection()

    monkeypatch.setattr(probes.socket, "create_connection", _create_connection)

    assert probes.is_endpoint_reachable("https://example.test/mcp") is True
    assert probes.is_endpoint_reachable("http://example.test/mcp") is True
    assert seen == [("example.test", 443), ("example.test", 80)]


def test_is_endpoint_reachable_defaults_the_host() -> None:
    assert probes.is_endpoint_reachable("http://:1/mcp", timeout=0.05) is False


def test_classify_llm_error_detects_connection_failures() -> None:
    assert probes.classify_llm_error(RuntimeError("Connection refused"))[0] == "connection_error"
    assert probes.classify_llm_error(RuntimeError("timed out"))[0] == "connection_error"


def test_classify_llm_error_keeps_other_errors_generic() -> None:
    assert probes.classify_llm_error(RuntimeError("bad request")) == ("error", "bad request")


def test_check_llm_health_reports_offline_without_connecting(monkeypatch) -> None:
    monkeypatch.setattr(probes, "is_endpoint_reachable", lambda url, timeout: False)

    healthy, message = asyncio.run(probes.check_llm_health("http://llm", "key", "model"))

    assert healthy is False
    assert message == probes.OFFLINE_MESSAGE


def test_check_llm_health_reports_success(monkeypatch) -> None:
    class _Models:
        async def list(self) -> list[Any]:
            return []

    class _FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.models = _Models()

    monkeypatch.setattr(probes, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(probes, "AsyncOpenAI", _FakeOpenAI)

    healthy, message = asyncio.run(probes.check_llm_health("http://llm", "key", "model"))

    assert healthy is True
    assert message == "LLM backend is reachable."


def test_check_llm_health_reports_connection_errors(monkeypatch) -> None:
    class _Models:
        async def list(self) -> list[Any]:
            raise RuntimeError("connection refused")

    class _FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.models = _Models()

    monkeypatch.setattr(probes, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(probes, "AsyncOpenAI", _FakeOpenAI)

    healthy, message = asyncio.run(probes.check_llm_health("http://llm", "key", "model"))

    assert healthy is False
    assert message == "connection_error: connection refused"


def test_list_models_reports_offline_without_connecting(monkeypatch) -> None:
    monkeypatch.setattr(probes, "is_endpoint_reachable", lambda url, timeout: False)

    models, message = asyncio.run(probes.list_models("http://llm", "key"))

    assert models == []
    assert message == probes.OFFLINE_MESSAGE


def test_list_models_returns_sorted_unique_ids(monkeypatch) -> None:
    class _Model:
        def __init__(self, model_id: str) -> None:
            self.id = model_id

    class _Models:
        async def list(self) -> Any:
            return type("Page", (), {"data": [_Model("b"), _Model("a"), _Model("b"), _Model("")]})()

    class _FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.models = _Models()

    monkeypatch.setattr(probes, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(probes, "AsyncOpenAI", _FakeOpenAI)

    models, message = asyncio.run(probes.list_models("http://llm", "key"))

    assert models == ["a", "b"]
    assert message is None


def test_list_models_explains_why_a_provider_cannot_answer(monkeypatch) -> None:
    class _Models:
        async def list(self) -> Any:
            raise RuntimeError("connection refused")

    class _FakeOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.models = _Models()

    monkeypatch.setattr(probes, "is_endpoint_reachable", lambda url, timeout: True)
    monkeypatch.setattr(probes, "AsyncOpenAI", _FakeOpenAI)

    models, message = asyncio.run(probes.list_models("http://llm", "key"))

    assert models == []
    assert message == "connection_error: connection refused"


def test_defaults_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_BASE_URL", "http://llm/v1")
    monkeypatch.setenv("AGENTIC_ODI_API_KEY", "secret")
    monkeypatch.setenv("AGENTIC_ODI_MODEL", "model")
    monkeypatch.setenv("AGENTIC_ODI_MCP_URL", "http://mcp")

    assert probes.defaults() == {
        "base_url": "http://llm/v1",
        "api_key": "secret",
        "model_name": "model",
        "mcp_url": "http://mcp",
    }
