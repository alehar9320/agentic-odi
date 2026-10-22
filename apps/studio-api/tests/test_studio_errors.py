"""HTTP error shape, status mapping, and request-id correlation."""

from __future__ import annotations

from agentic_odi_core.remote import StudioError, StudioErrorCode
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio.errors import StudioHTTPError
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_unknown_api_route_returns_the_error_shape() -> None:
    client = _client(create_app(InMemoryRepository()))

    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["request_id"]
    assert response.headers["X-Request-ID"] == body["error"]["request_id"]


def test_validation_failure_returns_the_error_shape() -> None:
    client = _client(create_app(InMemoryRepository()))

    response = client.post("/api/jobs", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation"
    assert body["error"]["detail"]
    assert body["error"]["suggestion"] == "Check the request body and try again."


def test_studio_http_error_keeps_its_code_and_status() -> None:
    app = create_app(InMemoryRepository())

    @app.get("/api/boom")
    def boom():
        raise StudioHTTPError(
            StudioError(code=StudioErrorCode.OUT_OF_RANGE, message="out of range")
        )

    response = _client(app).get("/api/boom")

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "out_of_range"
    assert body["error"]["message"] == "out of range"


def test_request_id_header_is_echoed() -> None:
    client = _client(create_app(InMemoryRepository()))

    response = client.get("/health", headers={"X-Request-ID": "test-123"})

    assert response.headers["X-Request-ID"] == "test-123"


def test_unhandled_exception_returns_the_error_shape() -> None:
    app = create_app(InMemoryRepository())

    @app.get("/api/kaput")
    def kaput():
        raise RuntimeError("secret internal detail")

    response = _client(app).get("/api/kaput")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal"
    assert body["error"]["request_id"]
    assert response.headers["X-Request-ID"] == body["error"]["request_id"]
    assert "secret internal detail" not in response.text


def test_unknown_api_route_is_not_swallowed_by_the_spa(monkeypatch, tmp_path) -> None:
    from agentic_odi_studio_api import app as app_module

    (tmp_path / "index.html").write_text("<html>studio</html>")
    monkeypatch.setattr(app_module, "SPA_DIST", tmp_path)

    response = _client(create_app(InMemoryRepository())).get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
