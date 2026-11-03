"""How these tests read a failing tool's answer.

A failure now carries a machine-readable envelope inside the text, so asserting
on the raw string would couple every test to prose that core already
classifies. ``failure`` returns the typed error the production parser builds,
which is what a client branches on; ``sentence`` returns the human half, which
is what a client that only reads text sees.
"""

from __future__ import annotations

import json

from agentic_odi_core.remote import StudioError, parse_tool_result


def failure(text: str) -> StudioError:
    error = parse_tool_result(text)
    assert error is not None, text
    return error


def sentence(text: str) -> str:
    return str(json.loads(text)["message"])
