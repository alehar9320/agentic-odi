"""Line-reading helpers shared by the keyboard passes.

The candidate review pass (``interviews review``) and the scoring pass
(``score``) both read one key per step from stdin, show a refusal without
ending the pass, and treat end-of-input as a quit. Keeping the reading in one
place means the two passes behave the same at the keyboard and in a script.
"""

from __future__ import annotations

import sys

import typer


class EndOfInput(Exception):
    """Raised when a prompt reaches end-of-input instead of a key."""


def read_line(label: str, *, quiet: bool = False) -> str:
    """Prompt with ``label`` and read one line, or raise on end-of-input.

    ``quiet`` suppresses the prompt (``--json`` mode emits only the JSON summary
    on stdout, so the prompts would corrupt it). A blank line is an empty
    string; end-of-input is distinct so a caller can treat it as a quit rather
    than a skip.
    """
    if not quiet:
        typer.echo(label, nl=False, err=True)
    raw = sys.stdin.readline()
    if raw == "":
        raise EndOfInput
    return raw.rstrip("\n")


def read_score(label: str, provided: float | None, *, quiet: bool = False) -> float:
    """Read a 1–10 score, or return the value the caller already supplied."""
    if provided is not None:
        return provided
    return float(read_line(f"{label} (1.0-10.0): ", quiet=quiet).strip())


def warn(message: str, *, quiet: bool = False) -> None:
    """Show a refusal to the person, unless ``--json`` must keep stdout clean."""
    if not quiet:
        typer.secho(message, fg="red", err=True)
