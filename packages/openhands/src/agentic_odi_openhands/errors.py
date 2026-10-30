"""Errors raised by the OpenHands client.

A caller needs to tell apart "retry later" from "fix the key" from "the agent
is blocked", so the hierarchy is explicit. Messages never include request
headers, API keys, or session keys.
"""

from __future__ import annotations


class OpenHandsError(Exception):
    """Base class for every client failure."""


class AuthError(OpenHandsError):
    """401/403: the configured key or auth header is wrong."""


class RateLimitError(OpenHandsError):
    """429: back off and retry."""


class TransientError(OpenHandsError):
    """5xx or a network failure: retry with backoff."""


class UnexpectedResponseError(OpenHandsError):
    """The response did not match the wire shape the client expected."""


class NotFoundError(OpenHandsError):
    """404: the conversation, sandbox, or task does not exist."""
