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

TAURI_CONF = "apps/studio/src-tauri/tauri.conf.json"
TAURI_CARGO = "apps/studio/src-tauri/Cargo.toml"

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


def _toml_value(toml_path: Path, table: str, key: str) -> str:
    """Return ``key = "value"`` for ``key`` under ``[table]``.

    Hand-parsed rather than with ``tomllib`` so the suite still runs on
    Python 3.10 (the test matrix's floor), mirroring ``_declared_version``.
    """
    section = re.compile(r"^\[" + re.escape(table) + r"\]\s*$")
    line_re = re.compile(rf'^{re.escape(key)}\s*=\s*"([^"]+)"\s*$')
    in_section = False
    for line in toml_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("["):
            in_section = bool(section.match(line))
            continue
        if in_section:
            match = line_re.match(line)
            if match:
                return match.group(1)
    raise AssertionError(f"no {key} in [{table}] in {toml_path}")


def _json_value(json_path: Path, key: str) -> str:
    """Return the string value of ``key`` from a flat JSON object."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    try:
        return str(data[key])
    except KeyError as exc:
        raise AssertionError(f"no {key} in {json_path}") from exc


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


def test_tauri_and_cargo_versions_match_the_released_version() -> None:
    # The Living Studio desktop shell keeps its own version in both
    # tauri.conf.json and Cargo.toml. release-please bumps both via extra-files,
    # so they must not drift from the release version.
    released = _released_version()

    cargo_version = _toml_value(ROOT / TAURI_CARGO, "package", "version")
    tauri_version = _json_value(ROOT / TAURI_CONF, "version")

    assert cargo_version == released, (
        f"Cargo.toml package.version ({cargo_version}) != release ({released})"
    )
    assert tauri_version == released, (
        f"tauri.conf.json version ({tauri_version}) != release ({released})"
    )
