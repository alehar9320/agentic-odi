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
CACHE_PATH_ENV = "AGENTIC_ODI_CONNECTORS_CACHE"
MARKETPLACE_CACHE_PATH_ENV = "AGENTIC_ODI_MARKETPLACE_CACHE"


def config_path() -> Path:
    """Return the path to the shared ``connectors.json`` registry file."""
    env = os.getenv(CONFIG_PATH_ENV)
    if env:
        return Path(env)
    return Path.home() / ".config" / "agentic-odi" / "connectors.json"


def cache_path() -> Path:
    """Return the path to the shared connector health cache file."""
    env = os.getenv(CACHE_PATH_ENV)
    if env:
        return Path(env)
    return Path.home() / ".cache" / "agentic-odi" / "connector-health.json"


def marketplace_cache_path() -> Path:
    """Return the path to the marketplace search cache file."""
    env = os.getenv(MARKETPLACE_CACHE_PATH_ENV)
    if env:
        return Path(env)
    return Path.home() / ".cache" / "agentic-odi" / "marketplace.json"


__all__ = [
    "CACHE_PATH_ENV",
    "CONFIG_PATH_ENV",
    "MARKETPLACE_CACHE_PATH_ENV",
    "cache_path",
    "config_path",
    "marketplace_cache_path",
]
