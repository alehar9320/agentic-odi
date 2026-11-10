"""Give the contract's Studio clients the sidecar's own bearer token.

The parity tests compare the CLI/MCP surfaces against the Studio API. That API
is gated, so a bare ``TestClient`` answers 401; these tests assert parity of
data, not authorisation (which is covered by ``test_studio_auth.py``).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolate_studio_memory(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_DB", str(tmp_path / "studio.db"))
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_TOKEN", str(tmp_path / "studio-token"))


@pytest.fixture(autouse=True)
def authenticated_clients(monkeypatch: pytest.MonkeyPatch):
    original_init = TestClient.__init__

    def __init__(self, *args, **kwargs):
        app = kwargs.get("app") or (args[0] if args else None)
        token = getattr(getattr(app, "state", None), "studio_token", None)
        if token:
            headers = dict(kwargs.get("headers") or {})
            headers.setdefault("Authorization", f"Bearer {token}")
            kwargs["headers"] = headers
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(TestClient, "__init__", __init__)
