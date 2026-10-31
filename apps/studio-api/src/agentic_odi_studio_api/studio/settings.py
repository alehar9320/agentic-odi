"""Settings the sidecar owns, so a provider key never lives in a browser.

``localStorage`` is readable by any script on the page and travels with the
profile, which makes it the wrong place for a secret. The key is written to one
small file next to the data store, mode ``0600``, and the SPA is only ever
handed a redacted form: it can show *"configured — sk-…4f2a"* without ever
holding the value it sent.
"""

from __future__ import annotations

import json
import os
import stat
import threading
from pathlib import Path
from typing import Any

CONFIG_FIELDS = ("base_url", "model", "mcp_url")


def default_settings_path() -> Path:
    configured = os.environ.get("AGENTIC_ODI_STUDIO_SETTINGS")
    if configured:
        return Path(configured)
    return Path.home() / ".agentic-odi" / "studio.json"


def mask_key(key: str) -> str:
    """A form safe to show: enough to recognise the key, none of the key."""
    stripped = key.strip()
    if not stripped:
        return ""
    if len(stripped) <= 8:
        return f"{stripped[:2]}…"
    return f"{stripped[:3]}…{stripped[-4:]}"


class StudioSettings:
    """The sidecar's own config file, with the provider key kept private."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = default_settings_path() if path is None else Path(path)
        self._lock = threading.RLock()
        self._values: dict[str, Any] = self._read()

    def _read(self) -> dict[str, Any]:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError:
            return {}
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self._values, indent=2), encoding="utf-8")
        os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        temporary.replace(self.path)
        os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)

    @property
    def api_key(self) -> str:
        with self._lock:
            return str(self._values.get("api_key") or "")

    def resolve_api_key(self, supplied: str | None) -> str:
        """A client that stopped sending the secret still gets the configured one."""
        if supplied:
            return supplied
        return self.api_key

    def update(self, values: dict[str, Any]) -> None:
        """Apply a partial update. ``api_key=None`` means "leave it alone"."""
        with self._lock:
            for field in CONFIG_FIELDS:
                if field in values:
                    self._values[field] = str(values.get(field) or "")
            key = values.get("api_key")
            if key is not None:
                cleaned = str(key).strip()
                if cleaned:
                    self._values["api_key"] = cleaned
                else:
                    self._values.pop("api_key", None)
            self._write()

    def redacted(self) -> dict[str, Any]:
        with self._lock:
            key = self.api_key
            return {
                **{field: str(self._values.get(field) or "") for field in CONFIG_FIELDS},
                "has_api_key": bool(key),
                "masked": mask_key(key),
            }


__all__ = ["CONFIG_FIELDS", "StudioSettings", "default_settings_path", "mask_key"]
