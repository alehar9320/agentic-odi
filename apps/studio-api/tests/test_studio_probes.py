"""Tests for endpoint probing and LLM health classification."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any, cast

import pytest
from agentic_odi_studio_api.studio import probes
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)


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


def _status_error(exc_type: type[APIStatusError], status: int) -> Exception:
    """Build an SDK status error without importing httpx, which the SDK owns.

    The SDK only reads ``status_code``, ``headers``, ``request`` and ``text`` off
    the response, so a namespace is enough and keeps the test off an undeclared
    dependency.
    """

    response = SimpleNamespace(
        status_code=status,
        headers={},
        request=SimpleNamespace(method="POST", url="http://llm/v1/models", headers={}),
        text='{"error": {"message": "provider text"}}',
    )
    return exc_type("provider text", response=cast(Any, response), body=None)


def _connection_error(exc_type: type[APIConnectionError]) -> Exception:
    request = SimpleNamespace(method="POST", url="http://llm/v1/models")
    return exc_type(request=cast(Any, request))


@pytest.mark.parametrize(
    ("exc", "reason"),
    [
        (_status_error(AuthenticationError, 401), "auth"),
        (_status_error(PermissionDeniedError, 403), "forbidden"),
        (_status_error(NotFoundError, 404), "model_not_found"),
        (_status_error(RateLimitError, 429), "rate_limited"),
        (_connection_error(APIConnectionError), "connection_error"),
        (_connection_error(APITimeoutError), "connection_error"),
    ],
)
def test_classify_llm_error_reads_the_sdk_exception_type(exc: Exception, reason: str) -> None:
    classified, message = probes.classify_llm_error(exc)

    assert classified == reason
    assert "{" not in message
    assert "provider text" not in message


def test_classify_llm_error_does_not_leak_provider_json() -> None:
    _, message = probes.classify_llm_error(RuntimeError("boom"))

    assert "{" not in message


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
    assert message == f"connection_error: {probes.OFFLINE_MESSAGE}"


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
    assert message == f"connection_error: {probes.OFFLINE_MESSAGE}"


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


def test_load_profile_fallback_reads_utf8_non_ascii(monkeypatch, tmp_path) -> None:
    cfg_dir = tmp_path / "agentic-odi"
    cfg_dir.mkdir(parents=True)
    profile_file = cfg_dir / "llm_profile.json"
    profile_file.write_text(
        '{"model": "münchen-7b", "base_url": "http://localhost:8001/v1"}', encoding="utf-8"
    )

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    loaded = probes._load_profile_fallback()
    assert loaded.get("model") == "münchen-7b"
    assert loaded.get("base_url") == "http://localhost:8001/v1"


def test_the_profile_fallback_reads_the_one_config_directory(monkeypatch, tmp_path) -> None:
    from pathlib import Path

    from agentic_odi_core import settings

    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    profile_file = probes._profile_file()

    assert profile_file == Path(tmp_path) / ".config" / "agentic-odi" / "llm_profile.json"
    assert profile_file.parent == settings.config_dir()


def test_the_profile_fallback_reads_back_what_save_profile_writes(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    written = probes.save_profile({"model": "cli-written-7b"})

    assert written["model"] == "cli-written-7b"
    assert probes._load_profile_fallback()["model"] == "cli-written-7b"
    assert probes._profile_file().exists()
