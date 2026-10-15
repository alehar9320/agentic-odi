"""Error hierarchy shared by the connector registry and implementations."""

from __future__ import annotations

KNOWN_CONNECTOR_KINDS: tuple[str, ...] = ("mcp",)


class RegistryError(Exception):
    """Base class for connector registry errors."""


class UnknownConnectorKindError(RegistryError):
    """Raised when a connector kind is not recognised."""

    def __init__(self, name: str) -> None:
        self.name = name
        known = ", ".join(KNOWN_CONNECTOR_KINDS)
        super().__init__(f"unknown connector kind {name!r}; known kinds: {known}")


class DuplicateConnectorError(RegistryError):
    """Raised when two connectors share the same name."""


class ConnectorNotFoundError(RegistryError):
    """Raised when a connector cannot be found in the registry."""
