"""Tests for the per-install sidecar token file and its mode."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from agentic_odi_studio_api.studio.paths import (
    TOKEN_DIR_MODE,
    TOKEN_FILE_MODE,
    issue_token,
    load_token,
    token_path,
)


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


def test_issue_token_writes_a_0600_file_under_a_permissive_umask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_TOKEN", str(tmp_path / "studio-token"))
    # A permissive umask is what let the old code leave the token
    # world-readable on a shared machine.
    monkeypatch.setattr(os, "umask", lambda: 0o000)

    token = issue_token()

    path = tmp_path / "studio-token"
    assert path.is_file()
    assert path.read_text(encoding="utf-8") == token
    assert _mode(path) == TOKEN_FILE_MODE == 0o600
    assert _mode(path.parent) == TOKEN_DIR_MODE == 0o700


def test_issue_token_is_idempotent_and_keeps_the_existing_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_TOKEN", str(tmp_path / "studio-token"))
    monkeypatch.setattr(os, "umask", lambda: 0o000)

    first = issue_token()
    second = issue_token()

    assert first == second


def test_load_token_tightens_a_loose_existing_token_without_rotating_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "studio-token"
    path.write_text("a-loose-token", encoding="utf-8")
    os.chmod(path, 0o644)
    os.chmod(tmp_path, 0o755)
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_TOKEN", str(path))

    token = load_token()

    assert token == "a-loose-token"
    assert _mode(path) == 0o600
    assert _mode(path.parent) == 0o700


def test_load_token_returns_none_when_no_token_has_been_issued(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENTIC_ODI_STUDIO_TOKEN", str(tmp_path / "missing-token"))

    assert load_token() is None


def test_token_path_falls_back_to_the_profile_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTIC_ODI_STUDIO_TOKEN", raising=False)
    assert token_path() == Path.home() / ".config" / "agentic-odi" / "studio-token"
