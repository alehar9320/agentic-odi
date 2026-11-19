"""The one logging configuration every entrypoint shares.

Each process (CLI, MCP server, Studio sidecar) starts by calling
:func:`configure_logging`. Without it, whether an application logger's record
reaches a handler depends on whatever framework the process happens to be
running under — uvicorn installs its own, a bare ``python -m`` installs none —
so a warning that matters can vanish silently.

The configuration is deliberately small: stdlib ``logging``, one stderr handler,
one level. It is idempotent, so importing several entrypoints in one process
never doubles a line.
"""

from __future__ import annotations

import logging
import os

LOG_LEVEL_ENV = "AGENTIC_ODI_LOG_LEVEL"

DEFAULT_LEVEL = "INFO"

_configured = False


def configure_logging(level: str | None = None) -> None:
    """Configure the root logger once, honouring ``AGENTIC_ODI_LOG_LEVEL``.

    ``level`` wins when given; otherwise the environment variable is read and
    ``INFO`` is the default. An unrecognised level falls back to ``INFO`` rather
    than raising: a typo in a log level must not stop a process from starting.

    Calling this more than once is safe — the first call installs the handler,
    later calls do nothing. That guard is what keeps a process that runs several
    entrypoints (a test importing both the CLI and the sidecar) from printing
    every line twice.
    """
    global _configured
    if _configured:
        return

    resolved = level or os.environ.get(LOG_LEVEL_ENV) or DEFAULT_LEVEL
    numeric = logging.getLevelName(resolved.upper())
    if not isinstance(numeric, int):
        numeric = logging.INFO

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.set_name("agentic-odi")

    root = logging.getLogger()
    root.setLevel(numeric)
    root.addHandler(handler)

    _configured = True


__all__ = ["DEFAULT_LEVEL", "LOG_LEVEL_ENV", "configure_logging"]
