#!/usr/bin/env python3
"""Print the one version the workspace declares, or list every drift.

release-please bumps the root pyproject and every ``extra-files`` entry in
``release-please-config.json`` from the same tag, so all declared versions
must agree with ``.release-please-manifest.json``. A drift here is the bug
that shipped a desktop app reporting ``0.1.0`` at release ``0.12.0``.

``wrangler.jsonc`` is not an ``extra-files`` entry, so nothing bumps the
Worker's release identity automatically; its ``vars.RELEASE_VERSION`` is
checked here instead.

Parsed by hand rather than with ``tomllib`` because this must run on the
test matrix's Python 3.10 floor, where that module does not exist.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PYPROJECTS = (
    "pyproject.toml",
    "packages/core/pyproject.toml",
    "packages/connectors/pyproject.toml",
    "apps/cli/pyproject.toml",
    "apps/mcp-server/pyproject.toml",
    "apps/studio-api/pyproject.toml",
)
BUILD_INFO = "apps/cli/src/agentic_odi_cli/_build_info.py"
STUDIO_PACKAGE_JSON = "apps/studio/package.json"
TAURI_CONF = "apps/studio/src-tauri/tauri.conf.json"
TAURI_CARGO = "apps/studio/src-tauri/Cargo.toml"
WRANGLER_CONF = "wrangler.jsonc"

_PROJECT_SECTION = re.compile(r"^\[project\]\s*$")
_VERSION_LINE = re.compile(r'^version\s*=\s*"([^"]+)"\s*$')
_BUILD_INFO_VERSION = re.compile(r'^VERSION\s*=\s*"([^"]+)"')
# Unanchored, because the key sits inside `"vars": { ... }`, which may be
# written on one line or spread over several.
_WRANGLER_VERSION = re.compile(r'"RELEASE_VERSION"\s*:\s*"([^"]+)"')


def _declared_version(pyproject: Path) -> str:
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
    data = json.loads(json_path.read_text(encoding="utf-8"))
    try:
        return str(data[key])
    except KeyError as exc:
        raise AssertionError(f"no {key} in {json_path}") from exc


def _version_on_a_line(path: Path, pattern: re.Pattern[str], what: str) -> str:
    """Return the version ``pattern`` captures from the first line it matches.

    Uses ``search`` so a pattern anchors only where it says ``^``, which lets
    one key inside a nested object sit on the same line as its opening brace.
    """
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if match:
            return match.group(1)
    raise AssertionError(f"no {what} in {path}")


def released_version(root: Path) -> str:
    manifest = json.loads((root / ".release-please-manifest.json").read_text(encoding="utf-8"))
    return manifest["."]


def declared_versions(root: Path) -> list[tuple[str, str]]:
    """Every version the workspace declares, as ``(relative_path, version)``."""
    declared = [(rel, _declared_version(root / rel)) for rel in PYPROJECTS]
    declared.append(
        (BUILD_INFO, _version_on_a_line(root / BUILD_INFO, _BUILD_INFO_VERSION, "VERSION"))
    )
    declared.append((STUDIO_PACKAGE_JSON, _json_value(root / STUDIO_PACKAGE_JSON, "version")))
    declared.append((TAURI_CONF, _json_value(root / TAURI_CONF, "version")))
    declared.append((TAURI_CARGO, _toml_value(root / TAURI_CARGO, "package", "version")))
    # Scanned line by line rather than with `_json_value`: wrangler.jsonc is
    # JSONC, and `json.loads` rejects the comments that explain the config.
    declared.append(
        (
            WRANGLER_CONF,
            _version_on_a_line(root / WRANGLER_CONF, _WRANGLER_VERSION, "vars.RELEASE_VERSION"),
        )
    )
    return declared


def check_parity(root: Path) -> list[tuple[str, str, str]]:
    """Return ``(path, declared, released)`` for every file out of step."""
    released = released_version(root)
    return [
        (rel, declared, released)
        for rel, declared in declared_versions(root)
        if declared != released
    ]


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else ROOT
    drifts = check_parity(root)
    if drifts:
        for rel, declared, released in drifts:
            print(f"{rel}: {declared} != released {released}", file=sys.stderr)
        return 1
    print(released_version(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
