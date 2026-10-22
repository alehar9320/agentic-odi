"""Error types for Agentic ODI operations.

Every failure mode in the domain has a dedicated exception class so callers
can branch on the *kind* of failure instead of matching on message text. All
ODI errors inherit from :class:`OdiError`, so a single ``except OdiError``
catches anything this package raises deliberately.

Note that :class:`ValidationError` here is the *ODI contract* error. Pydantic's
own ``ValidationError`` remains available from ``pydantic`` and is unrelated.
"""

from __future__ import annotations


class OdiError(Exception):
    """Base class for every deliberate Agentic ODI failure."""


class ValidationError(OdiError, ValueError):
    """Input did not satisfy the ODI contract.

    Also a :class:`ValueError` so that callers written against the previous
    behaviour (which raised bare ``ValueError``) keep working unchanged.
    """


class NotFoundError(OdiError):
    """A referenced resource does not exist."""

    def __init__(self, resource_id: str, kind: str) -> None:
        self.resource_id = resource_id
        self.kind = kind
        super().__init__(f"{kind} not found: {resource_id}")


class ConflictError(OdiError):
    """The requested change conflicts with the current state."""


class RateLimitError(OdiError):
    """The caller exceeded an allowed rate or volume."""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: float | None = None
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message)


class StoreError(OdiError):
    """The persistence layer could not complete the operation."""


class SerializationError(OdiError):
    """A payload could not be converted to or from its wire format."""


_STATUS_BY_ERROR: tuple[tuple[type[OdiError], int], ...] = (
    (ValidationError, 400),
    (NotFoundError, 404),
    (ConflictError, 409),
    (RateLimitError, 429),
    (StoreError, 500),
    (SerializationError, 502),
)


def error_status(err: OdiError) -> int:
    """Map an ODI error onto the HTTP status code that best describes it.

    Unknown :class:`OdiError` subclasses fall back to ``500`` rather than
    raising, so a new error type can never break an error handler.
    """
    for error_type, status in _STATUS_BY_ERROR:
        if isinstance(err, error_type):
            return status
    return 500
