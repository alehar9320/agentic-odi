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
    """A referenced resource does not exist.

    ``hint`` is an optional sentence telling the caller what to do next. It is
    appended to the message so it survives into user-facing output.
    """

    def __init__(self, resource_id: str, kind: str, hint: str | None = None) -> None:
        self.resource_id = resource_id
        self.kind = kind
        self.hint = hint or ""
        message = f"{kind} not found: {resource_id}"
        if self.hint:
            message = f"{message}. {self.hint}"
        super().__init__(message)


class ConflictError(OdiError):
    """The requested change conflicts with the current state."""


class RateLimitError(OdiError):
    """The caller exceeded an allowed rate or volume."""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: float | None = None
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message)


class ConsentRequired(OdiError):
    """The agent tried to act on the workspace before the PM agreed to it."""


class StoreError(OdiError):
    """The persistence layer could not complete the operation."""


class StoreCorrupt(StoreError):
    """The database failed its integrity check and must not be read or written.

    Raised at open when the store is damaged, so a caller can stop and tell the
    person which file is damaged and where the last good copy is. The file is
    never deleted, rewritten, or replaced with an empty one: a damaged store
    fails reads rather than answering them with nothing.
    """

    def __init__(
        self,
        path: str,
        problems: list[str] | None = None,
        *,
        label: str = "Your database",
        detail: str | None = None,
    ) -> None:
        self.path = path
        self.problems = list(problems or [])
        self.label = label
        self.detail = detail
        count = len(self.problems)
        summary = f"{label} failed its integrity check: {path}"
        if count:
            summary = f"{summary} ({count} problem{'s' if count != 1 else ''} found)"
        super().__init__(summary)


class SerializationError(OdiError):
    """A payload could not be converted to or from its wire format."""


_STATUS_BY_ERROR: tuple[tuple[type[OdiError], int], ...] = (
    (ValidationError, 400),
    (NotFoundError, 404),
    (ConflictError, 409),
    (RateLimitError, 429),
    (ConsentRequired, 403),
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
