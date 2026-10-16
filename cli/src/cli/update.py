"""Self-update engine primitives (checksum, extraction, atomic version swap)."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

RELEASES_API = "https://api.github.com/repos/alehar9320/agentic-odi/releases/latest"

_SYSTEM_MAP = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}
_ARCH_MAP = {
    "x86_64": "x86_64",
    "AMD64": "x86_64",
    "arm64": "arm64",
    "aarch64": "arm64",
}


class UpdateError(Exception):
    """Raised when an update cannot be performed."""


def parse_version(s: str) -> tuple[int, int, int]:
    """Parse a version string into a ``(major, minor, patch)`` tuple."""
    cleaned = s.strip().lstrip("v")
    parts = cleaned.split(".")[:3]
    nums = [int(p) for p in parts]
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def is_newer(latest: str, current: str) -> bool:
    """Return True if ``latest`` is strictly newer than ``current``."""
    return parse_version(latest) > parse_version(current)


def asset_name(version: str, os_name: str, arch: str) -> str:
    """Return the release asset filename for a version/platform combination."""
    ext = "zip" if os_name == "windows" else "tar.gz"
    return f"odi_{version}_{os_name}_{arch}.{ext}"


def current_platform() -> tuple[str, str]:
    """Map the running host to the release ``(os, arch)`` identifiers."""
    os_name = _SYSTEM_MAP.get(platform.system(), platform.system().lower())
    arch = _ARCH_MAP.get(platform.machine(), platform.machine().lower())
    return os_name, arch


def verify_checksum(path: Path, expected_hex: str) -> bool:
    """Return True if the SHA-256 of ``path`` matches ``expected_hex``."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest().lower() == expected_hex.strip().lower()


def extract_archive(archive: Path, dest: Path) -> None:
    """Extract ``archive`` (``.zip`` or ``.tar.gz``) into ``dest``."""
    dest.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
    else:
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(dest)


def _acquire_lock(install_root: Path) -> tuple[int, Path]:
    lock_path = install_root / ".update.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise UpdateError("update already in progress") from exc
    return fd, lock_path


def _activate_version(version_dir: Path, install_root: Path) -> None:
    current = install_root / "current"
    if os.name == "nt":
        marker_tmp = install_root / "current.tmp"
        if marker_tmp.exists() or marker_tmp.is_symlink():
            marker_tmp.unlink()
        marker_tmp.write_text(str(version_dir))
        os.replace(marker_tmp, current)
        return

    tmp_link = install_root / "current.tmp"
    if tmp_link.is_symlink() or tmp_link.exists():
        tmp_link.unlink()
    os.symlink(version_dir, tmp_link)
    os.replace(tmp_link, current)


def perform_update(
    version: str,
    archive_path: Path,
    expected_sha: str,
    install_root: Path,
) -> Path:
    """Verify, extract, and atomically activate ``version``; return its dir."""
    install_root = Path(install_root)
    versions = install_root / "versions"
    versions.mkdir(parents=True, exist_ok=True)

    lock_fd, lock_path = _acquire_lock(install_root)
    try:
        if not verify_checksum(archive_path, expected_sha):
            raise UpdateError(f"checksum mismatch for {archive_path.name}")

        tmp_dir = Path(tempfile.mkdtemp(prefix=".extract-", dir=versions))
        final_dir = versions / version
        try:
            extract_archive(archive_path, tmp_dir)
            if final_dir.is_symlink() or final_dir.is_file():
                final_dir.unlink()
            elif final_dir.is_dir():
                shutil.rmtree(final_dir)
            os.replace(tmp_dir, final_dir)
        except BaseException:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise

        _activate_version(final_dir, install_root)
        return final_dir
    finally:
        os.close(lock_fd)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
