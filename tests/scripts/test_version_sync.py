"""The released version must be the version the workspace declares."""

from __future__ import annotations

import json
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[2]
PYPROJECTS = (
    "pyproject.toml",
    "packages/core/pyproject.toml",
    "packages/connectors/pyproject.toml",
    "apps/cli/pyproject.toml",
    "apps/mcp-server/pyproject.toml",
    "apps/studio-api/pyproject.toml",
)


def _released_version() -> str:
    manifest = json.loads((ROOT / ".release-please-manifest.json").read_text(encoding="utf-8"))
    return manifest["."]


def test_every_pyproject_declares_the_released_version() -> None:
    released = _released_version()
    stale = {
        rel: tomllib.loads((ROOT / rel).read_text(encoding="utf-8"))["project"]["version"]
        for rel in PYPROJECTS
        if tomllib.loads((ROOT / rel).read_text(encoding="utf-8"))["project"]["version"] != released
    }

    assert stale == {}


def test_the_committed_build_info_matches_the_released_version() -> None:
    # The binary build overwrites this file from the release tag; the committed
    # default is what a source checkout reports, so it must not lag behind.
    from agentic_odi_cli import _build_info

    assert _build_info.VERSION == _released_version()
