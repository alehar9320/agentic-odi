"""Resolve the shared connector configuration file path.

The path is shared by the CLI, the Living Studio sidecar, and the MCP
ingest connector so every entry point reads and writes the same
``connectors.json``. An explicit override is honored via the
``AGENTIC_ODI_CONNECTORS_CONFIG`` environment variable; otherwise the
config lives under the user's platform config directory.
"""

from __future__ import annotations

import os
from pathlib import Path

CONFIG_PATH_ENV = "AGENTIC_ODI_CONNECTORS_CONFIG"


def config_path() -> Path:
    """Return the path to the shared ``connectors.json`` registry file."""
    env = os.getenv(CONFIG_PATH_ENV)
    if env:
        return Path(env)
    return Path.home() / ".config" / "agentic-odi" / "connectors.json"


__all__ = ["CONFIG_PATH_ENV", "config_path"]
