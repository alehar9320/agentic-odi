import hashlib
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from cli import update


def test_parse_and_compare():
    assert update.parse_version("v1.2.3") == (1, 2, 3)
    assert update.is_newer("0.2.0", "0.1.0") is True
    assert update.is_newer("0.1.0", "0.1.0") is False
    assert update.is_newer("0.1.0", "0.2.0") is False


def test_asset_name():
    assert update.asset_name("0.1.0", "linux", "x86_64") == "odi_0.1.0_linux_x86_64.tar.gz"
    assert update.asset_name("0.1.0", "windows", "x86_64") == "odi_0.1.0_windows_x86_64.zip"


def test_current_platform_mapping(monkeypatch):
    monkeypatch.setattr(update.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(update.platform, "machine", lambda: "arm64")
    assert update.current_platform() == ("macos", "arm64")


def _make_archive(tmp_path: Path, version: str) -> tuple[Path, str]:
    payload = tmp_path / "stage" / version / "odi"
    payload.parent.mkdir(parents=True)
    payload.write_text("#!/bin/sh\necho odi")
    archive = tmp_path / f"odi_{version}_linux_x86_64.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(payload.parent, arcname=".")
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    return archive, sha


def test_perform_update_flips_current(tmp_path):
    archive, sha = _make_archive(tmp_path, "0.2.0")
    root = tmp_path / "install"
    version_dir = update.perform_update("0.2.0", archive, sha, root)
    assert version_dir == root / "versions" / "0.2.0"
    assert (root / "current").resolve() == version_dir.resolve()
    assert (version_dir / "odi").exists()


def test_perform_update_rejects_bad_checksum(tmp_path):
    archive, _ = _make_archive(tmp_path, "0.2.0")
    with pytest.raises(update.UpdateError):
        update.perform_update("0.2.0", archive, "deadbeef", tmp_path / "install")
    assert not (tmp_path / "install" / "current").exists()


def test_verify_checksum(tmp_path):
    p = tmp_path / "f"
    p.write_bytes(b"hello")
    good = hashlib.sha256(b"hello").hexdigest()
    assert update.verify_checksum(p, good) is True
    assert update.verify_checksum(p, "0" * 64) is False


def test_extract_archive_rejects_tar_path_traversal(tmp_path):
    archive = tmp_path / "evil.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo(name="../escape.txt")
        payload = b"pwned"
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))
    dest = tmp_path / "out"
    with pytest.raises((tarfile.TarError, update.UpdateError)):
        update.extract_archive(archive, dest)
    assert not (tmp_path / "escape.txt").exists()


def test_extract_archive_contains_zip_path_traversal(tmp_path):
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../evil.txt", "pwned")
    dest = tmp_path / "out"
    update.extract_archive(archive, dest)
    assert not (tmp_path / "evil.txt").exists()


def test_default_fetch_rejects_non_https(tmp_path):
    local = tmp_path / "payload.txt"
    local.write_text("secret")
    with pytest.raises(update.UpdateError):
        update._default_fetch(local.as_uri())
