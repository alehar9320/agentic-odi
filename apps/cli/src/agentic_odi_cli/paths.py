"""Path resolution utilities for the agentic-odi CLI."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def install_root() -> Path:
    """Resolve the installation root directory.

    Resolution order:
    1. AGENTIC_ODI_INSTALL_DIR env var
    2. XDG_DATA_HOME/agentic-odi (POSIX) or %LOCALAPPDATA%\\agentic-odi (Windows)
    3. ~/.local/share/agentic-odi (POSIX fallback)
    """
    env_install = os.environ.get("AGENTIC_ODI_INSTALL_DIR")
    if env_install:
        return Path(env_install).resolve()

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "agentic-odi"
        return Path.home() / "AppData" / "Local" / "agentic-odi"

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "agentic-odi"

    return Path.home() / ".local" / "share" / "agentic-odi"


def bin_dir() -> Path:
    """Resolve the binary directory.

    Resolution order:
    1. XDG_BIN_HOME (POSIX) or install_root()/bin (Windows)
    2. ~/.local/bin (POSIX fallback)
    """
    if sys.platform == "win32":
        return install_root() / "bin"

    xdg_bin_home = os.environ.get("XDG_BIN_HOME")
    if xdg_bin_home:
        return Path(xdg_bin_home)

    return Path.home() / ".local" / "bin"


def config_dir() -> Path:
    """Resolve the configuration directory.

    Resolution order:
    1. XDG_CONFIG_HOME/agentic-odi (POSIX)
    2. ~/.config/agentic-odi (POSIX fallback)
    3. %APPDATA%\\agentic-odi (Windows)
    """
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data) / "agentic-odi"
        return Path.home() / "AppData" / "Roaming" / "agentic-odi"

    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / "agentic-odi"

    return Path.home() / ".config" / "agentic-odi"


def versions_dir() -> Path:
    """Resolve the versions directory where installed versions are stored."""
    return install_root() / "versions"


def current_link() -> Path:
    """Resolve the 'current' symlink path."""
    return install_root() / "current"


def state_file() -> Path:
    """Resolve the update state file path."""
    return install_root() / "update.json"


def is_frozen() -> bool:
    """Check if the application is running in a frozen/packaged state."""
    return bool(getattr(sys, "frozen", False))


def is_writable_dir(p: Path) -> bool:
    """Check if the given path is a writable directory."""
    try:
        return p.is_dir() and os.access(p, os.W_OK)
    except Exception:  # noqa: BLE001
        return False
