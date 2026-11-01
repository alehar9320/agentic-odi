"""Content-Security-Policy headers on sidecar responses."""

from __future__ import annotations

from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_studio_api import app as app_module
from fastapi.testclient import TestClient


def _client() -> TestClient:
    return TestClient(app_module.create_app(InMemoryRepository()))


def test_csp_header_is_present_on_every_response() -> None:
    response = _client().get("/health")
    assert response.status_code == 200
    policy = response.headers.get("content-security-policy")
    assert policy is not None


def test_csp_forbids_unsafe_eval_and_inline_script() -> None:
    response = _client().get("/capabilities")
    assert response.status_code == 200
    policy = response.headers.get("content-security-policy")
    assert policy is not None
    assert "unsafe-eval" not in policy
    assert "unsafe-inline" not in policy
    assert "script-src *" not in policy


def test_csp_allows_only_self_for_scripts() -> None:
    response = _client().get("/health")
    policy = response.headers.get("content-security-policy")
    assert policy is not None
    assert "script-src 'self'" in policy
