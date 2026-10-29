"""Tests for the static SPA fallback and the local server entrypoint."""

from __future__ import annotations

from agentic_odi_core.messages import CAPABILITIES
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_studio_api import app as app_module
from agentic_odi_studio_api import main as main_module
from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(app_module.create_app(InMemoryRepository()))


def test_capabilities_endpoint_returns_the_capability_list() -> None:
    response = _client().get("/capabilities")

    assert response.status_code == 200
    assert response.json() == {"capabilities": CAPABILITIES}
    # The body must say what the assistant can do, not which backend is loaded.
    assert "Job Map" in response.json()["capabilities"]
    assert response.json()["capabilities"] != "local"


def test_spa_fallback_serves_index_for_unknown_routes(monkeypatch, tmp_path) -> None:
    (tmp_path / "index.html").write_text("<html>studio</html>")
    monkeypatch.setattr(app_module, "SPA_DIST", tmp_path)

    response = _client().get("/some/deep/route")

    assert response.status_code == 200
    assert response.text == "<html>studio</html>"


def test_spa_fallback_serves_existing_files(monkeypatch, tmp_path) -> None:
    (tmp_path / "index.html").write_text("<html>studio</html>")
    (tmp_path / "hello.txt").write_text("hello")
    monkeypatch.setattr(app_module, "SPA_DIST", tmp_path)

    response = _client().get("/hello.txt")

    assert response.status_code == 200
    assert response.text == "hello"


def test_spa_fallback_returns_404_without_index(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_module, "SPA_DIST", tmp_path)

    response = _client().get("/missing", headers={"X-Request-ID": "req-9"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert response.json()["error"]["request_id"] == "req-9"


def test_spa_fallback_can_be_disabled(monkeypatch, tmp_path) -> None:
    (tmp_path / "index.html").write_text("<html>studio</html>")
    monkeypatch.setattr(app_module, "SPA_DIST", tmp_path)
    monkeypatch.setenv("AGENTIC_ODI_DISABLE_SPA", "1")

    response = _client().get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_spa_assets_are_mounted(monkeypatch, tmp_path) -> None:
    (tmp_path / "index.html").write_text("<html>studio</html>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('studio')")
    monkeypatch.setattr(app_module, "SPA_DIST", tmp_path)

    response = _client().get("/assets/app.js")

    assert response.status_code == 200
    assert response.text == "console.log('studio')"


def test_main_runs_uvicorn_with_the_sidecar_factory(monkeypatch) -> None:
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(
        main_module.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs))
    )

    main_module.main()

    assert calls == [
        (
            ("agentic_odi_studio_api.app:create_app",),
            {"factory": True, "host": "127.0.0.1", "port": 8100},
        )
    ]
