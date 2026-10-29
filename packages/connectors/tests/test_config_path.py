from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _no_stale_env(monkeypatch):
    monkeypatch.delenv("AGENTIC_ODI_CONNECTORS_CONFIG", raising=False)


def test_config_path_uses_explicit_env(monkeypatch, tmp_path):
    from agentic_odi_connectors.paths import config_path

    target = tmp_path / "custom" / "connectors.json"
    monkeypatch.setenv("AGENTIC_ODI_CONNECTORS_CONFIG", str(target))

    assert config_path() == target


def test_config_path_default_under_config_dir(monkeypatch, tmp_path):
    from agentic_odi_connectors.paths import config_path

    fake_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(fake_home))

    expected = fake_home / ".config" / "agentic-odi" / "connectors.json"
    assert config_path() == expected


def test_config_path_returns_path_instance():
    from agentic_odi_connectors.paths import config_path

    assert isinstance(config_path(), Path)
