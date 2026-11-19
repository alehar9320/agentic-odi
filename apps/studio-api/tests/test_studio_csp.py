"""Content-Security-Policy headers on sidecar responses."""

from __future__ import annotations

import base64
import hashlib

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


def _policy_for(monkeypatch, tmp_path) -> str:
    (tmp_path / "index.html").write_text("<html>studio</html>")
    monkeypatch.setattr(app_module, "SPA_DIST", tmp_path)
    response = _client().get("/health")
    return response.headers["content-security-policy"]


def test_the_offline_document_inline_blocks_are_allowed_by_hash(monkeypatch, tmp_path) -> None:
    """#546's page must stay self-contained, so the policy names its blocks.

    A hash admits those exact bytes and nothing else: the policy still refuses
    inline script and inline style everywhere a reply could be injected.
    """
    script = 'var theme = "light";'
    style = "body { background: #0a0b0e; }"
    (tmp_path / "offline.html").write_text(
        f"<html><head><script>{script}</script><style>{style}</style></head></html>"
    )

    policy = _policy_for(monkeypatch, tmp_path)

    for body in (script, style):
        digest = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode("ascii")
        assert f"'sha256-{digest}'" in policy
    # The allowance is a hash, never a blanket inline exception.
    assert "unsafe-inline" not in policy
    assert "script-src 'self' 'sha256-" in policy
    assert "style-src 'self' 'sha256-" in policy


def test_an_absent_offline_document_leaves_the_policy_alone(monkeypatch, tmp_path) -> None:
    assert _policy_for(monkeypatch, tmp_path) == app_module.CSP_POLICY
