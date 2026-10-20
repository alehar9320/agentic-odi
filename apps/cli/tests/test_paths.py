import sys

import pytest
from agentic_odi_cli import paths


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


def test_install_root_windows_uses_local_app_data(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    assert paths.install_root() == tmp_path / "local" / "agentic-odi"


def test_install_root_windows_falls_back_to_appdata_home(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert paths.install_root() == tmp_path / "AppData" / "Local" / "agentic-odi"


def test_bin_dir_honours_xdg_bin_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_BIN_HOME", str(tmp_path / "bin"))

    assert paths.bin_dir() == tmp_path / "bin"


def test_bin_dir_defaults_to_local_bin(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_BIN_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert paths.bin_dir() == tmp_path / ".local" / "bin"


def test_config_dir_defaults_to_dot_config(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert paths.config_dir() == tmp_path / ".config" / "agentic-odi"


def test_bin_dir_windows_uses_the_install_root(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("AGENTIC_ODI_INSTALL_DIR", str(tmp_path / "root"))

    assert paths.bin_dir() == tmp_path / "root" / "bin"


def test_config_dir_windows_uses_app_data(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))

    assert paths.config_dir() == tmp_path / "roaming" / "agentic-odi"


def test_config_dir_windows_falls_back_to_appdata_home(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    assert paths.config_dir() == tmp_path / "AppData" / "Roaming" / "agentic-odi"


def test_is_writable_dir_returns_false_on_errors(monkeypatch, tmp_path):
    def _boom(path, mode):
        raise OSError("denied")

    monkeypatch.setattr(paths.os, "access", _boom)

    assert paths.is_writable_dir(tmp_path) is False
