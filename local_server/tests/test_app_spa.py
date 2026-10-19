"""Tests for the static SPA fallback and the local server entrypoint."""

from __future__ import annotations

from core.repository import InMemoryRepository
from fastapi.testclient import TestClient

from local_server import app as app_module
from local_server import main as main_module


def _client() -> TestClient:
    return TestClient(app_module.create_app(InMemoryRepository()))


def test_capabilities_endpoint_reports_local() -> None:
    response = _client().get("/capabilities")

    assert response.status_code == 200
    assert response.json() == {"capabilities": "local"}


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

    response = _client().get("/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_spa_fallback_can_be_disabled(monkeypatch, tmp_path) -> None:
    (tmp_path / "index.html").write_text("<html>studio</html>")
    monkeypatch.setattr(app_module, "SPA_DIST", tmp_path)
    monkeypatch.setenv("AGENTIC_ODI_DISABLE_SPA", "1")

    response = _client().get("/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


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
            ("local_server.app:create_app",),
            {"factory": True, "host": "127.0.0.1", "port": 8100},
        )
    ]
