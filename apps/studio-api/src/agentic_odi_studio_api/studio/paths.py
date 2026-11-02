"""Resolve the per-install sidecar token and issue one on first run.

The token lives in the user's profile directory so every local process
(Studio sidecar, MCP server, browser client) shares the same key for one
install. It is issued lazily on first use and reused thereafter.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

TOKEN_PATH_ENV = "AGENTIC_ODI_STUDIO_TOKEN"


def token_path() -> Path:
    """Return the path to the per-install sidecar token file."""
    env = os.getenv(TOKEN_PATH_ENV)
    if env:
        return Path(env)
    return Path.home() / ".config" / "agentic-odi" / "studio-token"


def load_token() -> str | None:
    """Return the stored token, or ``None`` when none has been issued yet."""
    path = token_path()
    if not path.is_file():
        return None
    token = path.read_text(encoding="utf-8").strip()
    return token or None


def issue_token() -> str:
    """Issue (or return) the per-install sidecar token."""
    path = token_path()
    if path.is_file():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    return token
