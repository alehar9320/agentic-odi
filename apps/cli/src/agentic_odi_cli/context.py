"""Global CLI context: selected backend and connection options."""

from __future__ import annotations

import os

from agentic_odi_cli.backend import BackendConfig

_config = BackendConfig()


def set_options(
    backend: str | None = None,
    db_path: str | None = None,
    mcp_url: str | None = None,
) -> None:
    """Record the global ``--backend/--db/--mcp-url`` options for this run."""
    global _config
    _config = BackendConfig(backend=backend, db_path=db_path, mcp_url=mcp_url)


def config() -> BackendConfig:
    return _config


def selected_backend() -> str:
    return _config.backend or os.environ.get("AGENTIC_ODI_BACKEND", "local")
