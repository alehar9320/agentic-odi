"""Canonical path resolution for the ODI and Studio databases.

The CLI, the Studio sidecar, and the recovery helpers all need to agree on
where the two local SQLite files live. Keeping the resolution here — and not
reconstructing it in each caller — means a person who sets an environment
variable sees the same path everywhere, and a future move of the data
directory is a one-line change instead of three.

Nothing in this module opens a file or creates a directory: it only resolves
the path the *current configuration* points at, whether or not the file exists.
"""

from __future__ import annotations

import os
from pathlib import Path

#: Directory ODI data files live under, relative to the user's home.
DEFAULT_DATA_DIR_NAME = ".agentic-odi"

#: Default filename for the ODI store.
DEFAULT_ODI_DB_NAME = "odi.db"

#: Default filename for the Studio memory store.
DEFAULT_STUDIO_DB_NAME = "studio.db"

#: Environment variable that overrides the ODI database path.
ODI_DB_ENV = "AGENTIC_ODI_DB"

#: Environment variable that overrides the Studio database path.
STUDIO_DB_ENV = "AGENTIC_ODI_STUDIO_DB"


def default_data_dir() -> Path:
    """Resolve the directory ODI data files live under."""
    return Path(os.path.expanduser("~")) / DEFAULT_DATA_DIR_NAME


def default_odi_db_path() -> Path:
    """Resolve the default path for the ODI database.

    Resolution order:

    1. ``AGENTIC_ODI_DB`` environment variable
    2. ``~/.agentic-odi/odi.db``
    """
    configured = os.environ.get(ODI_DB_ENV)
    if configured:
        return Path(configured)
    return default_data_dir() / DEFAULT_ODI_DB_NAME


def default_studio_db_path() -> Path:
    """Resolve the default path for the Studio memory database.

    Resolution order:

    1. ``AGENTIC_ODI_STUDIO_DB`` environment variable
    2. ``~/.agentic-odi/studio.db``
    """
    configured = os.environ.get(STUDIO_DB_ENV)
    if configured:
        return Path(configured)
    return default_data_dir() / DEFAULT_STUDIO_DB_NAME
