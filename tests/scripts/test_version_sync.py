"""The released version must be the version the workspace declares."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYPROJECTS = (
    "pyproject.toml",
    "packages/core/pyproject.toml",
    "packages/connectors/pyproject.toml",
    "apps/cli/pyproject.toml",
    "apps/mcp-server/pyproject.toml",
    "apps/studio-api/pyproject.toml",
)

_PROJECT_SECTION = re.compile(r"^\[project\]\s*$")
_VERSION_LINE = re.compile(r'^version\s*=\s*"([^"]+)"\s*$')


def _declared_version(pyproject: Path) -> str:
    """Return the ``version`` declared in the file's ``[project]`` table.

    Parsed by hand rather than with ``tomllib`` because the test suite still
    runs on Python 3.10, where that module does not exist.
    """
    in_project = False
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.startswith("["):
            in_project = bool(_PROJECT_SECTION.match(line))
            continue
        if in_project:
            match = _VERSION_LINE.match(line)
            if match:
                return match.group(1)
    raise AssertionError(f"no [project] version in {pyproject}")


def _released_version() -> str:
    manifest = json.loads((ROOT / ".release-please-manifest.json").read_text(encoding="utf-8"))
    return manifest["."]


def test_every_pyproject_declares_the_released_version() -> None:
    released = _released_version()
    stale = {
        rel: _declared_version(ROOT / rel)
        for rel in PYPROJECTS
        if _declared_version(ROOT / rel) != released
    }

    assert stale == {}


def test_the_committed_build_info_matches_the_released_version() -> None:
    # The binary build overwrites this file from the release tag; the committed
    # default is what a source checkout reports, so it must not lag behind.
    from agentic_odi_cli import _build_info

    assert _build_info.VERSION == _released_version()
