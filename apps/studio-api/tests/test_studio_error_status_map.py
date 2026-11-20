"""Status-to-error-code mapping and retryability for sidecar HTTP errors.

A 401, 403, 405 or 429 from the sidecar used to render as ``code: "internal"``
and was never retryable, so the client could not distinguish a refused token or
a rate limit from a server crash. These tests pin the new status -> code table.
"""

from __future__ import annotations

import pytest

from agentic_odi_core.remote import StudioErrorCode, retryable_for_code
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio.errors import (
    STATUS_FOR_CODE,
    code_for_status,
    status_for_code,
)
from fastapi.testclient import TestClient


def _client(app) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "unauthorized"),
        (403, "forbidden"),
        (405, "method_not_allowed"),
        (429, "rate_limited"),
        (503, "unavailable"),
    ],
)
def test_status_maps_to_its_own_code(status: int, code: str) -> None:
    assert code_for_status(status).value == code


def test_status_and_code_maps_are_exact_inverses() -> None:
    for status in STATUS_FOR_CODE.values():
        assert status_for_code(code_for_status(status)) == status


def test_status_reachable_from_a_status_is_never_internal() -> None:
    for status in (401, 403, 405, 413, 415, 429, 503):
        assert code_for_status(status) is not StudioErrorCode.INTERNAL


def test_retryable_flags() -> None:
    assert retryable_for_code(StudioErrorCode.RATE_LIMITED) is True
    assert retryable_for_code(StudioErrorCode.UNAVAILABLE) is True
    for code in (
        StudioErrorCode.UNAUTHORIZED,
        StudioErrorCode.FORBIDDEN,
        StudioErrorCode.METHOD_NOT_ALLOWED,
        StudioErrorCode.PAYLOAD_TOO_LARGE,
        StudioErrorCode.UNSUPPORTED_MEDIA_TYPE,
        StudioErrorCode.VALIDATION,
        StudioErrorCode.NOT_FOUND,
    ):
        assert retryable_for_code(code) is False


def test_wrong_method_returns_405_not_retryable(monkeypatch) -> None:
    monkeypatch.setenv("AGENTIC_ODI_DISABLE_SPA", "1")
    app = create_app(InMemoryRepository())
    response = _client(app).post("/api/capabilities")
    assert response.status_code == 405
    body = response.json()
    assert body["error"]["code"] == "method_not_allowed"
    assert body["error"]["retryable"] is False
