"""Validated process settings, read from the environment in exactly one place.

Every ``AGENTIC_ODI_*`` variable a process reads is declared here as a Pydantic
field whose ``alias`` is the variable name, and ``from_env()`` is the only entry
point. A value that cannot be parsed raises :class:`ConfigurationError` naming
the variable, the value, and the form it accepts — instead of silently becoming
the default, which is how ``AGENTIC_ODI_MCP_TIMEOUT=30s`` used to read as thirty
seconds with nobody told.

``os.environ`` is read here and nowhere else in ``packages/core``; a direct read
elsewhere is drift this module exists to prevent.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, Field

from agentic_odi_core.errors import ConfigurationError

DEFAULT_MCP_TIMEOUT = 30.0
DEFAULT_MCP_KEEPALIVE = 15.0

TIMEOUT_ENV = "AGENTIC_ODI_MCP_TIMEOUT"
KEEPALIVE_ENV = "AGENTIC_ODI_MCP_KEEPALIVE"


def _raw(name: str) -> str | None:
    """The variable's value with surrounding space trimmed, or ``None``.

    An unset variable and an empty one are the same thing: neither is a value,
    so both fall back to the default.
    """
    value = os.environ.get(name)
    if value is None:
        return None
    return value.strip() or None


def positive_float(name: str, default: float) -> float:
    """Read ``name`` as a number greater than zero, or fall back to ``default``."""
    raw = _raw(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigurationError(
            f"{name}={raw!r} is not a number; use a number of seconds, for example {name}=30"
        ) from None
    if value <= 0:
        raise ConfigurationError(
            f"{name}={raw!r} must be greater than zero; use a number of seconds, for example {name}=30"
        )
    return value


def non_negative_float_or_none(name: str, default: float) -> float | None:
    """Read ``name`` as a number of seconds; ``0`` means "disabled" (``None``)."""
    raw = _raw(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigurationError(
            f"{name}={raw!r} is not a number; use a number of seconds, or 0 to disable it"
        ) from None
    if value < 0:
        raise ConfigurationError(
            f"{name}={raw!r} must be zero or greater; use a number of seconds, or 0 to disable it"
        )
    return value or None


class MCPConnectionSettings(BaseModel):
    """How long an MCP client waits, and how often it keeps a session alive.

    ``keepalive_interval`` is ``None`` when keepalive is disabled.
    """

    model_config = ConfigDict(populate_by_name=True, frozen=True)

    timeout: float = Field(default=DEFAULT_MCP_TIMEOUT, alias=TIMEOUT_ENV, gt=0)
    keepalive_interval: float | None = Field(
        default=DEFAULT_MCP_KEEPALIVE, alias=KEEPALIVE_ENV, ge=0
    )

    @classmethod
    def from_env(cls) -> MCPConnectionSettings:
        """Build the settings from the environment, or raise on a bad value."""
        return cls(
            timeout=positive_float(TIMEOUT_ENV, DEFAULT_MCP_TIMEOUT),
            keepalive_interval=non_negative_float_or_none(KEEPALIVE_ENV, DEFAULT_MCP_KEEPALIVE),
        )
