import hashlib
import json

import pytest
from agentic_odi_cli import update


def test_should_check_within_and_after_interval(tmp_path):
    state = tmp_path / "update.json"
    assert update.should_check(state, now=1000.0) is True
    update.record_check(state, now=1000.0)
    assert update.should_check(state, now=1000.0 + 100) is False
    assert update.should_check(state, now=1000.0 + update.CHECK_INTERVAL_SECONDS + 1) is True
    assert json.loads(state.read_text())["last_check"] == 1000.0


def test_latest_release_offline_returns_none():
    def boom(_url):
        raise OSError("network down")

    assert update.latest_release("0.1.0", fetch=boom) is None


def test_latest_release_returns_none_when_current():
    payload = json.dumps({"tag_name": "v0.1.0"})
    assert update.latest_release("0.1.0", fetch=lambda _u: payload) is None


def test_latest_release_returns_newer():
    payload = json.dumps({"tag_name": "v0.2.0"})
    assert update.latest_release("0.1.0", fetch=lambda _u: payload) == "0.2.0"


def test_auto_update_enabled_matrix(monkeypatch):
    assert update.auto_update_enabled(no_update=False) is True
    assert update.auto_update_enabled(no_update=True) is False
    monkeypatch.setenv("AGENTIC_ODI_NO_UPDATE", "1")
    assert update.auto_update_enabled(no_update=False) is False


def test_maybe_auto_update_disabled_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_INSTALL_DIR", str(tmp_path / "install"))
    assert update.maybe_auto_update(no_update=True, now=1000.0) is None


def test_download_writes_and_verifies(tmp_path):
    version = "0.2.0"
    asset = update.asset_name(version, *update.current_platform())
    payload = b"fake-archive-bytes"
    digest = hashlib.sha256(payload).hexdigest()
    checksums = f"{digest}  {asset}\n{'0' * 64}  something-else.tar.gz\n"
    requested: list[str] = []

    def fetch_bytes(url: str) -> bytes:
        requested.append(url)
        if url.endswith("checksums.txt"):
            return checksums.encode("utf-8")
        return payload

    dest = tmp_path / "downloads"
    archive = update.download(version, dest, fetch_bytes=fetch_bytes)

    assert archive == dest / asset
    assert archive.read_bytes() == payload
    assert any(url.endswith("checksums.txt") for url in requested)
    assert any(url.endswith(asset) for url in requested)


def test_download_raises_on_checksum_mismatch(tmp_path):
    version = "0.2.0"
    asset = update.asset_name(version, *update.current_platform())
    checksums = f"{'0' * 64}  {asset}\n"

    def fetch_bytes(url: str) -> bytes:
        if url.endswith("checksums.txt"):
            return checksums.encode("utf-8")
        return b"fake-archive-bytes"

    with pytest.raises(update.UpdateError):
        update.download(version, tmp_path / "downloads", fetch_bytes=fetch_bytes)
