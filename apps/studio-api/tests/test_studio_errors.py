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


def test_studio_http_error_keeps_its_code_and_status(monkeypatch) -> None:
    # A built SPA (`apps/studio/dist` from a local `npm run build`) registers a
    # catch-all route when the app is created, which would shadow the route added
    # below. The error shape is the subject here, not how the SPA is served.
    monkeypatch.setenv("AGENTIC_ODI_DISABLE_SPA", "1")
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


def test_unhandled_exception_returns_the_error_shape(monkeypatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_DISABLE_SPA", "1")
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


def test_unhandled_exception_surfaces_the_request_id_in_the_message(monkeypatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_DISABLE_SPA", "1")
    app = create_app(InMemoryRepository())

    @app.get("/api/kaput")
    def kaput():
        raise RuntimeError("secret internal detail")

    response = _client(app).get("/api/kaput", headers={"X-Request-ID": "req-9"})

    body = response.json()
    assert "req-9" in body["error"]["message"]
    assert body["error"]["message"].startswith("Something went wrong")


def test_unknown_api_route_is_not_swallowed_by_the_spa(monkeypatch, tmp_path) -> None:
    from agentic_odi_studio_api import app as app_module

    (tmp_path / "index.html").write_text("<html>studio</html>")
    monkeypatch.setattr(app_module, "SPA_DIST", tmp_path)

    response = _client(create_app(InMemoryRepository())).get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_chat_request_id_comes_from_the_header_not_the_body() -> None:
    client = _client(create_app(InMemoryRepository()))

    response = client.post(
        "/api/chat",
        json={
            "base_url": "http://llm/v1",
            "api_key": "k",
            "model": "m",
            "mcp_url": "http://mcp",
            "messages": [{"role": "user", "content": "hi"}],
            "request_id": "client-supplied",  # ignored: the header owns the id
        },
        headers={"X-Request-ID": "header-id"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "header-id"
    assert "client-supplied" not in response.text
    assert "header-id" in response.text


def test_an_unusable_request_id_is_replaced() -> None:
    client = _client(create_app(InMemoryRepository()))

    response = client.get(
        "/api/does-not-exist",
        headers={"X-Request-ID": "a" * 300},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["request_id"] != "a" * 300
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]


def test_the_spa_fallback_404_body_carries_the_request_id() -> None:
    from agentic_odi_studio_api import app as app_module

    client = _client(create_app(InMemoryRepository()))
    response = client.get("/api/does-not-exist", headers={"X-Request-ID": "req-9"})

    assert response.status_code == 404
    assert response.json()["error"]["request_id"] == "req-9"
    assert app_module is not None
