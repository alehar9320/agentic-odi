"""Self-update engine primitives (checksum, extraction, atomic version swap)."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from cli import paths
from cli.version import __version__

RELEASES_API = "https://api.github.com/repos/alehar9320/agentic-odi/releases/latest"
CHECK_INTERVAL_SECONDS = 86400
_RELEASES_DOWNLOAD = "https://github.com/alehar9320/agentic-odi/releases/download"

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


def should_check(state_file: Path, now: float) -> bool:
    """Return True if an update check is due (missing/corrupt state ⇒ due)."""
    try:
        data = json.loads(Path(state_file).read_text())
        last_check = float(data["last_check"])
    except (OSError, ValueError, KeyError, TypeError):
        return True
    return (now - last_check) >= CHECK_INTERVAL_SECONDS


def record_check(state_file: Path, now: float) -> None:
    """Persist the timestamp of the most recent check."""
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_check": now}))


def _default_fetch(url: str) -> str:
    with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310
        return response.read().decode("utf-8")


def _default_fetch_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310
        return response.read()


def latest_release(current: str, *, fetch: Callable[[str], str] | None = None) -> str | None:
    """Return the latest release version if newer than ``current``, else None."""
    fetcher = fetch if fetch is not None else _default_fetch
    try:
        payload = json.loads(fetcher(RELEASES_API))
        tag = str(payload["tag_name"]).strip()
    except Exception:  # noqa: BLE001
        return None
    latest = tag.lstrip("v")
    if is_newer(latest, current):
        return latest
    return None


def _parse_checksums(text: str, filename: str) -> str | None:
    """Return the SHA-256 hex for ``filename`` from a sha256sum-format body."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == filename:
            return parts[0]
    return None


def download(
    version: str,
    dest_dir: Path,
    *,
    fetch_bytes: Callable[[str], bytes] | None = None,
) -> Path:
    """Download and verify the release archive for ``version``."""
    fetcher = fetch_bytes if fetch_bytes is not None else _default_fetch_bytes
    base = f"{_RELEASES_DOWNLOAD}/v{version}"
    asset = asset_name(version, *current_platform())

    try:
        checksums = fetcher(f"{base}/checksums.txt").decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise UpdateError(f"failed to fetch checksums.txt: {exc}") from exc

    expected = _parse_checksums(checksums, asset)
    if expected is None:
        raise UpdateError(f"no checksum entry for {asset}")

    try:
        payload = fetcher(f"{base}/{asset}")
    except Exception as exc:  # noqa: BLE001
        raise UpdateError(f"failed to fetch {asset}: {exc}") from exc

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / asset
    dest.write_bytes(payload)
    if not verify_checksum(dest, expected):
        raise UpdateError(f"checksum mismatch for {asset}")
    return dest


def auto_update_enabled(no_update: bool) -> bool:
    """Return whether auto-update is enabled by the flag/env opt-outs."""
    return (not no_update) and (not os.environ.get("AGENTIC_ODI_NO_UPDATE"))


def maybe_auto_update(*, no_update: bool, now: float) -> str | None:
    """Best-effort background update; never raises, returns new version or None."""
    try:
        if not auto_update_enabled(no_update):
            return None
        root = paths.install_root()
        if not paths.is_frozen():
            return None
        if not paths.is_writable_dir(root):
            return None
        if (root / ".update.lock").exists():
            return None
        state = paths.state_file()
        if not should_check(state, now):
            return None
        record_check(state, now)
        version = latest_release(__version__)
        if version is None:
            return None
        with tempfile.TemporaryDirectory(prefix="odi-update-") as tmp:
            archive = download(version, Path(tmp))
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            perform_update(version, archive, digest, root)
        return version
    except Exception:  # noqa: BLE001
        return None
