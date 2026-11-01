"""The released version must be the version the workspace declares."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

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
STUDIO_PACKAGE_JSON = "apps/studio/package.json"

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


def test_the_studio_package_version_matches_the_released_version() -> None:
    # npm ci and the Tauri shell both read apps/studio/package.json, and
    # release-please bumps it via extra-files, so it must not drift either.
    released = _released_version()
    package_version = _json_value(ROOT / STUDIO_PACKAGE_JSON, "version")

    assert package_version == released, (
        f"apps/studio/package.json version ({package_version}) != release ({released})"
    )


def _clean_workspace(tmp_path: Path, released: str, wrangler: str | None = None) -> Path:
    """Write a workspace whose every declared version equals ``released``.

    The parity script reads each file by hand, so the fixture is real files
    rather than a mock. ``wrangler`` defaults to a var that agrees.
    """
    import check_version_parity

    files = {
        ".release-please-manifest.json": json.dumps({".": released}),
        "pyproject.toml": f'[project]\nversion = "{released}"\n',
        "packages/core/pyproject.toml": f'[project]\nversion = "{released}"\n',
        "packages/connectors/pyproject.toml": f'[project]\nversion = "{released}"\n',
        "apps/cli/pyproject.toml": f'[project]\nversion = "{released}"\n',
        "apps/mcp-server/pyproject.toml": f'[project]\nversion = "{released}"\n',
        "apps/studio-api/pyproject.toml": f'[project]\nversion = "{released}"\n',
        check_version_parity.BUILD_INFO: f'VERSION = "{released}"\n',
        check_version_parity.STUDIO_PACKAGE_JSON: json.dumps({"version": released}),
        check_version_parity.TAURI_CONF: json.dumps({"version": released}),
        check_version_parity.TAURI_CARGO: f'[package]\nversion = "{released}"\n',
        check_version_parity.WRANGLER_CONF: wrangler
        if wrangler is not None
        else _wrangler_with(released),
    }
    for rel, text in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return tmp_path


def _wrangler_with(version: str) -> str:
    return '{\n  "name": "agentic-odi",\n  "vars": { "RELEASE_VERSION": "' + version + '" }\n}\n'


def test_the_parity_script_sees_no_drift() -> None:
    import check_version_parity

    assert check_version_parity.check_parity(ROOT) == []


def test_the_worker_declares_the_released_version() -> None:
    # The hosted Studio answers /api/build from this var, so a Worker deployed
    # from a tag reports that tag. release-please does not bump wrangler.jsonc,
    # so nothing but the parity check keeps the two together. Asserted against
    # the real tree by name, because `check_parity(ROOT) == []` would also pass
    # on a workspace that stopped reading this file at all.
    import check_version_parity

    declared = dict(check_version_parity.declared_versions(ROOT))

    assert declared[check_version_parity.WRANGLER_CONF] == _released_version()


def test_a_drifted_worker_var_is_the_only_drift_the_script_reports(tmp_path: Path) -> None:
    import check_version_parity

    _clean_workspace(tmp_path, "9.9.9", wrangler=_wrangler_with("0.0.1"))

    assert check_version_parity.check_parity(tmp_path) == [("wrangler.jsonc", "0.0.1", "9.9.9")]


def test_a_workspace_without_the_worker_var_is_reported_as_wrangler_drift(
    tmp_path: Path,
) -> None:
    import check_version_parity

    _clean_workspace(tmp_path, "9.9.9", wrangler='{\n  "name": "agentic-odi"\n}\n')

    with pytest.raises(AssertionError, match="wrangler.jsonc"):
        check_version_parity.check_parity(tmp_path)


def test_the_parity_script_fails_on_a_drifted_workspace(tmp_path: Path) -> None:
    import check_version_parity

    _clean_workspace(tmp_path, "9.9.9")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")

    assert check_version_parity.check_parity(tmp_path) == [("pyproject.toml", "0.1.0", "9.9.9")]
