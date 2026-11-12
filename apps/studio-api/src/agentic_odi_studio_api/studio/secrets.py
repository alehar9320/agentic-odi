"""Write-only storage for the model key.

The key leaves the browser's ``localStorage`` for a file the sidecar owns, so
any script running in the page can no longer read it. The read path here
returns only *whether* a key is set and *when* -- never the value.

The store is a single JSON file in the user's profile directory, written with
``0600`` and its directory with ``0700``. A store that cannot be written fails
closed: the caller sees an error rather than a silently dropped key.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE_PATH_ENV = "AGENTIC_ODI_STUDIO_SECRETS"

MODEL_KEY_NAME = "model_key"


class SecretStoreError(RuntimeError):
    """The secret store could not be read or written."""


def secrets_path() -> Path:
    """Return the path to the per-install secret store."""
    env = os.getenv(STORE_PATH_ENV)
    if env:
        return Path(env)
    return Path.home() / ".config" / "agentic-odi" / "studio-secrets.json"


def _read() -> dict[str, Any]:
    path = secrets_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError) as exc:  # noqa: BLE001
        raise SecretStoreError("The secret store could not be read.") from exc


def _write(payload: dict[str, Any]) -> None:
    path = secrets_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, stat.S_IRWXU)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        tmp.replace(path)
    except OSError as exc:
        raise SecretStoreError("The secret store is not writable.") from exc


def set_model_key(value: str) -> str:
    """Store the model key and return the ISO timestamp it was set at."""
    set_at = datetime.now(timezone.utc).isoformat()
    payload = _read()
    payload[MODEL_KEY_NAME] = {"value": value, "set_at": set_at}
    _write(payload)
    return set_at


def load_model_key() -> str | None:
    """Return the stored model key, or ``None`` when none is set."""
    entry = _read().get(MODEL_KEY_NAME)
    if not isinstance(entry, dict):
        return None
    value = entry.get("value")
    return value if isinstance(value, str) and value else None


def model_key_status() -> dict[str, Any]:
    """Whether a model key is set, and when -- never the value."""
    entry = _read().get(MODEL_KEY_NAME)
    if not isinstance(entry, dict) or not entry.get("value"):
        return {"configured": False, "set_at": None}
    set_at = entry.get("set_at")
    return {"configured": True, "set_at": set_at if isinstance(set_at, str) else None}
