"""The provider key belongs to the sidecar's file, never to the browser."""

from __future__ import annotations

import json

import pytest
from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import router as router_module
from agentic_odi_studio_api.studio.settings import (
    StudioSettings,
    default_settings_path,
    mask_key,
)
from fastapi.testclient import TestClient

KEY = "sk-live-1234567890abcdef4f2a"


def _client(tmp_path) -> TestClient:
    return TestClient(
        create_app(InMemoryRepository(), settings=StudioSettings(tmp_path / "studio.json"))
    )


def test_mask_keeps_only_enough_to_recognise_a_key() -> None:
    assert mask_key(KEY) == "sk-…4f2a"
    assert mask_key("short") == "sh…"
    assert mask_key("   ") == ""


def test_the_form_handed_to_the_browser_has_no_field_named_api_key(tmp_path) -> None:
    settings = StudioSettings(tmp_path / "studio.json")
    settings.update({"api_key": KEY})

    redacted = settings.redacted()

    assert "api_key" not in redacted
    assert KEY not in json.dumps(redacted)


def test_settings_are_written_owner_readable_only(tmp_path) -> None:
    settings = StudioSettings(tmp_path / "studio.json")

    settings.update({"base_url": "http://llm:8001/v1", "model": "m", "api_key": KEY})
    path = tmp_path / "studio.json"

    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())["api_key"] == KEY


def test_settings_survive_a_restart(tmp_path) -> None:
    StudioSettings(tmp_path / "studio.json").update({"api_key": KEY, "mcp_url": "http://mcp"})

    reopened = StudioSettings(tmp_path / "studio.json")

    assert reopened.api_key == KEY
    assert reopened.redacted()["mcp_url"] == "http://mcp"


def test_an_empty_file_is_not_a_crash(tmp_path) -> None:
    path = tmp_path / "studio.json"
    path.write_text("{ not json", encoding="utf-8")

    assert StudioSettings(path).redacted() == {
        "base_url": "",
        "model": "",
        "mcp_url": "",
        "has_api_key": False,
        "masked": "",
    }


def test_no_key_supplied_falls_back_to_the_configured_one(tmp_path) -> None:
    settings = StudioSettings(tmp_path / "studio.json")
    settings.update({"api_key": KEY})

    assert settings.resolve_api_key("") == KEY
    assert settings.resolve_api_key(None) == KEY
    assert settings.resolve_api_key("sk-other") == "sk-other"


def test_an_omitted_key_is_left_alone_but_an_empty_one_is_forgotten(tmp_path) -> None:
    settings = StudioSettings(tmp_path / "studio.json")
    settings.update({"api_key": KEY})

    settings.update({"model": "another-model"})
    assert settings.api_key == KEY

    settings.update({"api_key": ""})
    assert settings.api_key == ""


def test_the_settings_home_is_the_shared_agentic_odi_directory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_SETTINGS", str(tmp_path / "elsewhere.json"))
    assert default_settings_path() == tmp_path / "elsewhere.json"

    monkeypatch.delenv("AGENTIC_ODI_STUDIO_SETTINGS", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_settings_path() == tmp_path / ".agentic-odi" / "studio.json"


# -- the routes the studio calls ---------------------------------------------


def test_get_settings_reports_only_a_mask(tmp_path) -> None:
    client = _client(tmp_path)
    client.post("/api/settings", json={"api_key": KEY, "model": "m"})

    body = client.get("/api/settings").json()

    assert body["has_api_key"] is True
    assert body["masked"] == "sk-…4f2a"
    assert KEY not in client.get("/api/settings").text


def test_post_settings_without_a_key_keeps_the_stored_one(tmp_path) -> None:
    client = _client(tmp_path)
    client.post("/api/settings", json={"api_key": KEY})

    updated = client.post("/api/settings", json={"base_url": "http://llm:8001/v1"}).json()

    assert updated["has_api_key"] is True
    assert updated["base_url"] == "http://llm:8001/v1"


def test_the_stored_key_is_the_one_a_chat_turn_uses(tmp_path, monkeypatch) -> None:
    """The browser stops sending the secret; the sidecar supplies it."""
    seen: list[str] = []

    async def fake_stream_chat(request, *args, **kwargs):
        seen.append(request.api_key)
        yield 'event: message\ndata: {"content": "ok"}\n\n'

    monkeypatch.setattr(router_module, "stream_chat", fake_stream_chat)
    client = _client(tmp_path)
    client.post("/api/settings", json={"api_key": KEY})

    response = client.post(
        "/api/chat",
        json={
            "base_url": "http://llm:1/v1",
            "model": "m",
            "mcp_url": "http://mcp:1/mcp",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )

    assert response.status_code == 200
    assert seen == [KEY]
    assert KEY not in response.text


def test_the_config_endpoint_still_leaks_nothing(tmp_path) -> None:
    client = _client(tmp_path)
    client.post("/api/settings", json={"api_key": KEY})

    assert KEY not in client.get("/api/config").text
