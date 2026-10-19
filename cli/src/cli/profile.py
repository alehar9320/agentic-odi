"""Profile model, XDG config path, atomic load/save, and `setup`/`profile` Typer sub-app."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import typer

app = typer.Typer(name="profile", help="Profile management commands")

BASELINE_FILE_NAME = "baseline.json"


@dataclass
class Baseline:
    schema_version: int = 1
    created_at: str | None = None
    source: str | None = None
    product_name: str | None = None
    product_url: str | None = None
    domain: str | None = None
    primary_user: str | None = None
    business_model: str | None = None
    core_problem: str | None = None
    current_focus: str | None = None
    confidence: str | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "source": self.source,
            "product_name": self.product_name,
            "product_url": self.product_url,
            "domain": self.domain,
            "primary_user": self.primary_user,
            "business_model": self.business_model,
            "core_problem": self.core_problem,
            "current_focus": self.current_focus,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Baseline:
        kwargs = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**kwargs)


def config_dir() -> Path:
    """Return the XDG config dir for agentic-odi.

    Uses XDG_CONFIG_HOME if set; otherwise falls back to HOME/agentic-odi.
    """
    xdg = os.getenv("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "agentic-odi"
    home = Path(os.getenv("HOME", ""))
    return home / "agentic-odi"


def baseline_file() -> Path:
    """Return the path to the baseline JSON file."""
    return config_dir() / BASELINE_FILE_NAME


def baseline_exists() -> bool:
    """Return True if the baseline file exists and is parseable."""
    return baseline_file().exists()


def load_baseline() -> Baseline | None:
    """Load the baseline file, returning None if it does not exist.

    Raises ValueError on unparseable JSON.
    """
    if not baseline_exists():
        return None
    try:
        with open(baseline_file()) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Failed to parse baseline file: {e}") from e
    return Baseline.from_dict(data)


def save_baseline(b: Baseline) -> Path:
    """Save the baseline atomically, setting created_at ISO-8601 UTC when None."""
    cfg_dir = config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    b = (
        b
        if b.created_at is not None
        else Baseline(
            **{k: v for k, v in b.to_dict().items() if k != "created_at"},
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    )
    target = baseline_file()
    tmp = target.with_name(target.name + ".tmp")
    with open(tmp, "w") as f:
        f.write(json.dumps(b.to_dict()))
    os.replace(tmp, target)
    return target


def backup_baseline() -> Path | None:
    """Copy the existing baseline file to a dated backup.

    Returns the path of the backup file, or None if no existing file.
    """
    if not baseline_exists():
        return None
    import shutil

    backup_path = baseline_file().with_name(
        f"baseline.json.bak-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    shutil.copy2(baseline_file(), backup_path)
    return backup_path
