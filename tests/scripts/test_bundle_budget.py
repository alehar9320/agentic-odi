"""The cold-start bundle budget gate (#529).

The gate is a script, so it is tested as one: a synthetic build output with a
manifest and chunk files is run through `scripts/check_bundle_budget.mjs`, and
the exit code and message are what the test asserts. Nothing here mocks the
script — the real Node program reads real files.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_bundle_budget.mjs"


def _node_available() -> bool:
    return shutil.which("node") is not None


pytestmark = pytest.mark.skipif(
    not _node_available(), reason="the budget gate is a Node script"
)


def _write_manifest(dist: Path, entry_bytes: int, vendor_bytes: int = 0) -> Path:
    """A minimal Vite manifest with one entry and an optional vendor import."""
    assets = dist / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "index.js").write_bytes(b"x" * entry_bytes)

    manifest: dict[str, dict] = {
        "index.html": {
            "file": "assets/index.js",
            "isEntry": True,
            "imports": [],
        }
    }
    if vendor_bytes:
        (assets / "vendor.js").write_bytes(b"v" * vendor_bytes)
        manifest["_vendor.js"] = {"file": "assets/vendor.js", "name": "vendor"}
        manifest["index.html"]["imports"] = ["_vendor.js"]

    manifest_path = dist / ".vite" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _run(manifest: Path, baseline: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "node",
            str(SCRIPT),
            "--manifest",
            str(manifest),
            "--baseline",
            str(baseline),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_update_records_the_measured_entry(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path / "dist", entry_bytes=2048)
    baseline = tmp_path / "bundle-budget.json"

    result = _run(manifest, baseline, "--update")

    assert result.returncode == 0, result.stderr
    recorded = json.loads(baseline.read_text(encoding="utf-8"))
    assert recorded["entryBytes"] == 2048
    assert recorded["entryFile"] == "assets/index.js"


def test_within_tolerance_passes(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path / "dist", entry_bytes=2048)
    baseline = tmp_path / "bundle-budget.json"
    assert _run(manifest, baseline, "--update").returncode == 0

    # Grow the entry by 10%, inside the 20% tolerance.
    _write_manifest(tmp_path / "dist", entry_bytes=2252)
    result = _run(manifest, baseline)

    assert result.returncode == 0, result.stderr
    assert "within budget" in result.stdout


def test_beyond_tolerance_fails_and_names_the_delta(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path / "dist", entry_bytes=2048)
    baseline = tmp_path / "bundle-budget.json"
    assert _run(manifest, baseline, "--update").returncode == 0

    # Double the entry: a synthetic large import must fail the gate.
    _write_manifest(tmp_path / "dist", entry_bytes=4096)
    result = _run(manifest, baseline)

    assert result.returncode == 1
    assert "over the" in result.stderr
    assert "ceiling" in result.stderr


def test_cold_total_includes_static_imports(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path / "dist", entry_bytes=1024, vendor_bytes=4096)
    baseline = tmp_path / "bundle-budget.json"

    result = _run(manifest, baseline, "--update")

    recorded = json.loads(baseline.read_text(encoding="utf-8"))
    assert recorded["entryBytes"] == 1024
    assert recorded["coldBytes"] == 1024 + 4096
    assert len(recorded["coldChunks"]) == 2
    assert result.returncode == 0


def test_missing_manifest_explains_the_build_step(tmp_path: Path) -> None:
    result = _run(tmp_path / "nope" / "manifest.json", tmp_path / "baseline.json")

    assert result.returncode == 1
    assert "Build the Studio first" in result.stderr
