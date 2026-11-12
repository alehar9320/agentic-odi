"""The model key leaves the browser for the sidecar's write-only store.

The store keeps the value; every read path reports only whether a key is set
and when. The last test in this file is the one that matters: the value must
appear in no response body, on any route.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import secrets
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolate_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(secrets.STORE_PATH_ENV, str(tmp_path / "studio-secrets.json"))


def _client() -> TestClient:
    app = create_app(InMemoryRepository())
    token = app.state.studio_token
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


def test_put_then_get_reports_state_and_never_the_value() -> None:
    client = _client()

    written = client.put("/api/settings/model-key", json={"value": "sk-DO-NOT-LEAK"})
    assert written.status_code == 200
    body = written.json()
    assert body["configured"] is True
    assert isinstance(body["set_at"], str) and body["set_at"]

    read = client.get("/api/settings/model-key")
    assert read.status_code == 200
    assert read.json()["configured"] is True
    assert read.json()["set_at"] == body["set_at"]


def test_get_before_a_key_is_set_reports_not_configured() -> None:
    client = _client()
    response = client.get("/api/settings/model-key")
    assert response.status_code == 200
    assert response.json() == {"configured": False, "set_at": None}


def test_config_reports_key_state_not_the_value() -> None:
    client = _client()
    client.put("/api/settings/model-key", json={"value": "sk-DO-NOT-LEAK"})

    body = client.get("/api/config").json()

    assert body["model_key"]["configured"] is True
    assert "api_key" not in json.dumps(body["model_key"])
    assert "sk-DO-NOT-LEAK" not in json.dumps(body)


def test_empty_key_is_refused() -> None:
    client = _client()
    response = client.put("/api/settings/model-key", json={"value": "   "})
    assert response.status_code == 422


def test_stored_key_is_not_echoed_by_any_route() -> None:
    client = _client()
    client.put("/api/settings/model-key", json={"value": "sk-DO-NOT-LEAK"})

    for path in ("/api/config", "/api/settings/model-key", "/api/diagnostics"):
        text = client.get(path).text
        assert "sk-DO-NOT-LEAK" not in text, path


def test_store_file_is_written_with_owner_only_permissions() -> None:
    client = _client()
    client.put("/api/settings/model-key", json={"value": "sk-DO-NOT-LEAK"})

    path = secrets.secrets_path()
    assert path.is_file()
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == (stat.S_IRUSR | stat.S_IWUSR)


def test_unwritable_store_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A store path inside a file cannot be created, so the write must raise
    # rather than silently drop the key.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv(secrets.STORE_PATH_ENV, str(blocker / "nested" / "secrets.json"))

    with pytest.raises(secrets.SecretStoreError):
        secrets.set_model_key("sk-DO-NOT-LEAK")
