"""Edge-case tests for the self-update engine and background updater."""

from __future__ import annotations

import hashlib
import os
import tarfile
from pathlib import Path

import pytest
from agentic_odi_cli import update


def _archive(tmp_path: Path, version: str) -> tuple[Path, str]:
    payload = tmp_path / "stage" / version / "odi"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_text("#!/bin/sh\necho odi")
    archive = tmp_path / f"odi_{version}_linux_x86_64.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(payload.parent, arcname=".")
    return archive, hashlib.sha256(archive.read_bytes()).hexdigest()


def test_parse_version_pads_missing_components() -> None:
    assert update.parse_version("2") == (2, 0, 0)
    assert update.parse_version("v2.1") == (2, 1, 0)


def test_perform_update_rejects_a_concurrent_lock(tmp_path: Path) -> None:
    archive, sha = _archive(tmp_path, "0.2.0")
    root = tmp_path / "install"
    root.mkdir()
    (root / ".update.lock").write_text("held")

    with pytest.raises(update.UpdateError, match="already in progress"):
        update.perform_update("0.2.0", archive, sha, root)


def test_perform_update_replaces_a_file_with_a_directory(tmp_path: Path) -> None:
    archive, sha = _archive(tmp_path, "0.2.0")
    root = tmp_path / "install"
    (root / "versions").mkdir(parents=True)
    (root / "versions" / "0.2.0").write_text("stale")

    version_dir = update.perform_update("0.2.0", archive, sha, root)

    assert version_dir.is_dir()
    assert (version_dir / "odi").exists()
    assert not (root / ".update.lock").exists()


def test_perform_update_replaces_an_existing_version_directory(tmp_path: Path) -> None:
    archive, sha = _archive(tmp_path, "0.2.0")
    root = tmp_path / "install"
    stale = root / "versions" / "0.2.0"
    stale.mkdir(parents=True)
    (stale / "old.txt").write_text("old")

    version_dir = update.perform_update("0.2.0", archive, sha, root)

    assert version_dir.is_dir()
    assert not (version_dir / "old.txt").exists()


def test_perform_update_cleans_up_on_extraction_failure(tmp_path: Path, monkeypatch) -> None:
    archive, sha = _archive(tmp_path, "0.2.0")
    root = tmp_path / "install"

    def _boom(*args, **kwargs):
        raise RuntimeError("bad archive")

    monkeypatch.setattr(update, "extract_archive", _boom)

    with pytest.raises(RuntimeError, match="bad archive"):
        update.perform_update("0.2.0", archive, sha, root)

    leftovers = list((root / "versions").glob(".extract-*"))
    assert leftovers == []
    assert not (root / ".update.lock").exists()


def test_perform_update_tolerates_a_vanished_lock_file(tmp_path: Path, monkeypatch) -> None:
    archive, sha = _archive(tmp_path, "0.2.0")
    root = tmp_path / "install"
    root.mkdir()
    fd = os.open(root / "fd", os.O_CREAT | os.O_WRONLY)
    missing_lock = root / "missing.lock"
    monkeypatch.setattr(update, "_acquire_lock", lambda _root: (fd, missing_lock))

    version_dir = update.perform_update("0.2.0", archive, sha, root)

    assert version_dir.is_dir()


def test_activate_version_uses_a_marker_on_windows(tmp_path: Path, monkeypatch) -> None:
    install_root = tmp_path / "install"
    install_root.mkdir()
    (install_root / "current.tmp").write_text("stale")
    version_dir = install_root / "versions" / "0.2.0"
    version_dir.mkdir(parents=True)
    monkeypatch.setattr(update.os, "name", "nt")

    update._activate_version(version_dir, install_root)

    assert (install_root / "current").read_text() == str(version_dir)
    assert not (install_root / "current.tmp").exists()


def test_activate_version_replaces_a_stale_symlink(tmp_path: Path) -> None:
    install_root = tmp_path / "install"
    install_root.mkdir()
    (install_root / "current.tmp").write_text("stale")
    version_dir = install_root / "versions" / "0.2.0"
    version_dir.mkdir(parents=True)

    update._activate_version(version_dir, install_root)

    assert (install_root / "current").resolve() == version_dir.resolve()


class _Response:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def test_default_fetchers_read_https_responses(monkeypatch) -> None:
    monkeypatch.setattr(update.urllib.request, "urlopen", lambda url, timeout: _Response(b"body"))

    assert update._default_fetch("https://example.test") == "body"
    assert update._default_fetch_bytes("https://example.test") == b"body"


def test_parse_checksums_returns_none_without_a_match() -> None:
    assert update._parse_checksums("abc  other.txt", "wanted.txt") is None


def _asset(version: str) -> str:
    return update.asset_name(version, *update.current_platform())


def test_download_wraps_a_checksum_fetch_failure(tmp_path: Path) -> None:
    def _boom(url: str) -> bytes:
        raise OSError("offline")

    with pytest.raises(update.UpdateError, match="failed to fetch checksums.txt"):
        update.download("0.2.0", tmp_path, fetch_bytes=_boom)


def test_download_requires_a_checksum_entry(tmp_path: Path) -> None:
    def _fetch(url: str) -> bytes:
        return b"deadbeef  other.tar.gz\n"

    with pytest.raises(update.UpdateError, match="no checksum entry"):
        update.download("0.2.0", tmp_path, fetch_bytes=_fetch)


def test_download_wraps_an_archive_fetch_failure(tmp_path: Path) -> None:
    asset = _asset("0.2.0")

    def _fetch(url: str) -> bytes:
        if url.endswith("checksums.txt"):
            return f"{'0' * 64}  {asset}\n".encode()
        raise OSError("offline")

    with pytest.raises(update.UpdateError, match=f"failed to fetch {asset}"):
        update.download("0.2.0", tmp_path, fetch_bytes=_fetch)


def _auto_update_paths(monkeypatch, root: Path) -> None:
    monkeypatch.setattr(update.paths, "install_root", lambda: root)
    monkeypatch.setattr(update.paths, "is_frozen", lambda: True)
    monkeypatch.setattr(update.paths, "is_writable_dir", lambda path: True)
    monkeypatch.setattr(update.paths, "state_file", lambda: root / "update.json")


def test_maybe_auto_update_installs_a_newer_release(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "install"
    root.mkdir()
    archive = root / "archive.tar.gz"
    archive.write_bytes(b"payload")
    _auto_update_paths(monkeypatch, root)
    installed: list[tuple] = []
    monkeypatch.setattr(update, "latest_release", lambda current: "0.3.0")
    monkeypatch.setattr(update, "download", lambda version, dest: archive)
    monkeypatch.setattr(update, "perform_update", lambda *args: installed.append(args))

    assert update.maybe_auto_update(no_update=False, now=1000.0) == "0.3.0"
    assert len(installed) == 1


@pytest.mark.parametrize(
    ("frozen", "writable", "lock", "latest"),
    [
        (False, True, False, "0.3.0"),
        (True, False, False, "0.3.0"),
        (True, True, True, "0.3.0"),
        (True, True, False, None),
    ],
)
def test_maybe_auto_update_skips_unavailable_paths(
    tmp_path: Path, monkeypatch, frozen, writable, lock, latest
) -> None:
    root = tmp_path / "install"
    root.mkdir()
    if lock:
        (root / ".update.lock").write_text("held")
    monkeypatch.setattr(update.paths, "install_root", lambda: root)
    monkeypatch.setattr(update.paths, "is_frozen", lambda: frozen)
    monkeypatch.setattr(update.paths, "is_writable_dir", lambda path: writable)
    monkeypatch.setattr(update.paths, "state_file", lambda: root / "update.json")
    monkeypatch.setattr(update, "latest_release", lambda current: latest)

    assert update.maybe_auto_update(no_update=False, now=1000.0) is None


def test_maybe_auto_update_skips_recent_checks(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "install"
    root.mkdir()
    _auto_update_paths(monkeypatch, root)
    update.record_check(root / "update.json", 1000.0)

    assert update.maybe_auto_update(no_update=False, now=1001.0) is None


def test_maybe_auto_update_swallows_failures(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "install"
    root.mkdir()
    _auto_update_paths(monkeypatch, root)

    def _boom(current: str) -> str:
        raise RuntimeError("network down")

    monkeypatch.setattr(update, "latest_release", _boom)

    assert update.maybe_auto_update(no_update=False, now=1000.0) is None
