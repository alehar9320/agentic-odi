"""Isolate each test's Studio memory database from the developer's home."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolate_studio_memory(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_DB", str(tmp_path / "studio.db"))
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_TOKEN", str(tmp_path / "studio-token"))


@pytest.fixture(autouse=True)
def authenticated_clients(request, monkeypatch: pytest.MonkeyPatch):
    """Give every test client the sidecar's own bearer token.

    The route tests here were written before ``/api`` was gated and assert routing
    and data, not authorisation; the gate itself is checked in ``test_studio_auth.py``,
    whose clients have to stay unauthenticated, so that file keeps the real client.
    """
    if request.node.path.name == "test_studio_auth.py":
        return

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
