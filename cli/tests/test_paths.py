import sys

import pytest

from cli import paths


def test_install_root_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTIC_ODI_INSTALL_DIR", str(tmp_path / "root"))
    assert paths.install_root() == tmp_path / "root"


def test_install_root_uses_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.delenv("AGENTIC_ODI_INSTALL_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert paths.install_root() == tmp_path / "data" / "agentic-odi"


def test_install_root_defaults_to_local_share(monkeypatch, tmp_path):
    monkeypatch.delenv("AGENTIC_ODI_INSTALL_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert paths.install_root() == tmp_path / ".local" / "share" / "agentic-odi"


def test_config_dir_uses_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert paths.config_dir() == tmp_path / "cfg" / "agentic-odi"


def test_derived_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTIC_ODI_INSTALL_DIR", str(tmp_path / "root"))
    assert paths.versions_dir() == tmp_path / "root" / "versions"
    assert paths.current_link() == tmp_path / "root" / "current"
    assert paths.state_file().name == "update.json"


def test_is_frozen_false_by_default():
    assert paths.is_frozen() is False


@pytest.mark.skipif(sys.platform == "win32", reason="posix permission semantics")
def test_is_writable_dir(tmp_path):
    assert paths.is_writable_dir(tmp_path) is True
