"""Feature flags management: defaults, persistence, querying, and environment overrides."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentic_odi_cli.profile import config_dir

FLAGS_FILE_NAME = "feature_flags.json"


@dataclass(frozen=True)
class FlagSpec:
    key: str
    description: str
    default: bool


DEFAULT_FLAGS: dict[str, FlagSpec] = {
    "experimental_connectors": FlagSpec(
        key="experimental_connectors",
        description="Enable experimental MCP connectors and ingest sources",
        default=False,
    ),
    "auto_update": FlagSpec(
        key="auto_update",
        description="Enable automatic CLI update checks on startup",
        default=True,
    ),
    "advanced_metrics": FlagSpec(
        key="advanced_metrics",
        description="Enable detailed latency & telemetry metrics in chat/CLI",
        default=False,
    ),
    "developer_mode": FlagSpec(
        key="developer_mode",
        description="Show developer debug information and raw MCP payload traces",
        default=False,
    ),
}


@dataclass
class FeatureFlags:
    """Store of feature flag states."""

    flags: dict[str, bool] = field(default_factory=dict)
    updated_at: str | None = None

    def get(self, key: str) -> bool:
        if key in self.flags:
            return self.flags[key]
        if key in DEFAULT_FLAGS:
            return DEFAULT_FLAGS[key].default
        return False

    def set(self, key: str, value: bool) -> None:
        self.flags[key] = value

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self.flags.clear()
        elif key in self.flags:
            del self.flags[key]

    def to_dict(self) -> dict[str, Any]:
        full_flags = {}
        for k in DEFAULT_FLAGS:
            full_flags[k] = self.get(k)
        for k, v in self.flags.items():
            full_flags[k] = v
        return {
            "flags": full_flags,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FeatureFlags:
        raw_flags = d.get("flags", {})
        flags = {k: bool(v) for k, v in raw_flags.items()}
        return cls(flags=flags, updated_at=d.get("updated_at"))


def flags_file() -> Path:
    return config_dir() / FLAGS_FILE_NAME


def load_flags() -> FeatureFlags:
    target = flags_file()
    if not target.exists():
        return FeatureFlags()
    try:
        with open(target, encoding="utf-8") as f:
            data = json.load(f)
        return FeatureFlags.from_dict(data)
    except Exception:  # noqa: BLE001
        return FeatureFlags()


def save_flags(flags: FeatureFlags) -> Path:
    cfg_dir = config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    flags.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    target = flags_file()
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(flags.to_dict(), indent=2))
    os.replace(tmp, target)
    return target


def is_enabled(key: str) -> bool:
    """Check if a feature flag is enabled with environment override support.

    Env var format: AGENTIC_ODI_FLAG_<KEY> (e.g. AGENTIC_ODI_FLAG_DEVELOPER_MODE=1)
    """
    env_var = f"AGENTIC_ODI_FLAG_{key.upper()}"
    if env_var in os.environ:
        val = os.environ[env_var].lower()
        return val in {"1", "true", "yes", "on"}
    return load_flags().get(key)
