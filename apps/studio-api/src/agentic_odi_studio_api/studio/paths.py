"""Resolve the per-install sidecar token and issue one on first run.

The token lives in the user's profile directory so every local process
(Studio sidecar, MCP server, browser client) shares the same key for one
install. It is issued lazily on first use and reused thereafter.

The token file is written with mode ``0o600`` and its directory with
``0o700`` so a shared machine cannot read the bearer capability that gates
the sidecar. Existing loose tokens are tightened on read, without being
rotated, so a previously issued token keeps working.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

TOKEN_PATH_ENV = "AGENTIC_ODI_STUDIO_TOKEN"  # nosec B105 - env var name, not a secret

# The token is a bearer capability, not a config value: it must not be
# readable by other users on a shared machine.
TOKEN_FILE_MODE = 0o600
TOKEN_DIR_MODE = 0o700


def token_path() -> Path:
    """Return the path to the per-install sidecar token file."""
    env = os.getenv(TOKEN_PATH_ENV)
    if env:
        return Path(env)
    return Path.home() / ".config" / "agentic-odi" / "studio-token"


def _tighten(path: Path) -> None:
    """Tighten the mode of a token file and its directory in place.

    Existing loose tokens are repaired without being rotated, so a token
    issued before this fix keeps working.
    """
    path.chmod(TOKEN_FILE_MODE)
    path.parent.chmod(TOKEN_DIR_MODE)


def load_token() -> str | None:
    """Return the stored token, or ``None`` when none has been issued yet."""
    path = token_path()
    if not path.is_file():
        return None
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        return None
    _tighten(path)
    return token


def issue_token() -> str:
    """Issue (or return) the per-install sidecar token."""
    path = token_path()
    if path.is_file():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            _tighten(path)
            return existing
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(TOKEN_DIR_MODE)
    # Write with an explicit mode rather than relying on the process umask,
    # so the token is never world- or group-readable on a shared machine.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, TOKEN_FILE_MODE)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token)
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    return token
