"""The spine guides' commands are checked against the live CLI, and run.

``docs/interviews.md``, ``docs/scoring.md`` and ``docs/decision.md`` are the
guides ALH-59 promises: each carries a runnable isolated-fixture sequence, and
each command and flag in those sequences is checked against the CLI that ships,
not copied from a plan. ``scripts/doc_check.py`` only confirms a command *name*
exists; this test is the stronger half the issue names — it walks every fenced
``agentic-odi`` line, fails on an unknown command or flag, and executes the
sequences against a disposable store so a command that cannot run fails the
build.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess  # nosec B404 - fixed argv list, no shell (see B603 note)
import sys
from pathlib import Path
from typing import Any

import click
import pytest
from agentic_odi_cli.cli import app
from typer.main import get_command

ROOT = Path(__file__).resolve().parents[1]
GUIDES = [
    ROOT / "docs" / "interviews.md",
    ROOT / "docs" / "scoring.md",
    ROOT / "docs" / "decision.md",
]

_BASH_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)
_ENTRY = ("agentic-odi", "odi")


def _command_tree() -> dict[tuple[str, ...], click.Command]:
    """Every leaf CLI command keyed by its ``(group, …, command)`` path."""
    root: Any = get_command(app)
    tree: dict[tuple[str, ...], click.Command] = {}

    def walk(command: Any, prefix: tuple[str, ...]) -> None:
        children = getattr(command, "commands", None) or {}
        if children:
            for name, child in children.items():
                walk(child, (*prefix, name))
        else:
            tree[prefix] = command

    walk(root, ())
    return tree


def _options(command: click.Command) -> set[str]:
    names: set[str] = set()
    for param in command.params:
        names.update(getattr(param, "opts", []))
        names.update(getattr(param, "secondary_opts", []))
    return names


def _documented_commands(guide: Path) -> list[list[str]]:
    """Every ``agentic-odi`` invocation in a guide, as an argv tail list.

    Line continuations (``\\``) are joined; comment and pipe/shell operators are
    stripped so only the command and its flags remain. Placeholders such as
    ``<outcome-id>`` are kept — the sequence runner substitutes them.
    """
    invocations: list[list[str]] = []
    text = guide.read_text(encoding="utf-8")
    for block in _BASH_BLOCK.findall(text):
        joined = block.replace("\\\n", " ")
        for raw in joined.splitlines():
            line = raw.split(" # ", 1)[0].strip()
            if not line or line.startswith("#"):
                continue
            # Drop a trailing redirect or pipeline; the command is what precedes.
            line = re.split(r"\s*[|>]\s*", line, maxsplit=1)[0].strip()
            tokens = shlex.split(line)
            if not tokens or tokens[0] not in _ENTRY:
                continue
            invocations.append(tokens[1:])
    return invocations


def _resolve_path(tokens: list[str], tree: dict[tuple[str, ...], click.Command]):
    """Longest command path in ``tokens`` that exists, plus its leftover args."""
    best: tuple[tuple[str, ...], int] | None = None
    for length in range(1, len(tokens) + 1):
        candidate = tuple(tokens[:length])
        if candidate in tree:
            best = (candidate, length)
    return best


@pytest.mark.parametrize("guide", GUIDES, ids=lambda p: p.name)
def test_every_documented_guide_command_exists(guide: Path) -> None:
    tree = _command_tree()
    for tokens in _documented_commands(guide):
        resolved = _resolve_path(tokens, tree)
        # _command_tree holds leaves only, so an unknown group or subcommand
        # resolves to nothing and fails here.
        assert resolved is not None, f"{guide.name}: unknown command {tokens!r}"


@pytest.mark.parametrize("guide", GUIDES, ids=lambda p: p.name)
def test_every_documented_guide_flag_exists(guide: Path) -> None:
    tree = _command_tree()
    for tokens in _documented_commands(guide):
        resolved = _resolve_path(tokens, tree)
        assert resolved is not None, f"{guide.name}: unknown command {tokens!r}"
        path, consumed = resolved
        command = tree[path]
        allowed = _options(command) | {"--help"}
        for token in tokens[consumed:]:
            if not token.startswith("-"):
                continue
            flag = token.split("=", 1)[0]
            assert flag in allowed, (
                f"{guide.name}: {' '.join(path)} has no flag {flag!r} "
                f"(documented flags: {sorted(allowed)})"
            )


def _run(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 - fixed argv list, no shell
        argv,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _extract_id(pattern: str, output: str) -> str:
    match = re.search(pattern, output)
    assert match, output
    return match.group(1)


def test_the_interviews_sequence_runs_end_to_end(tmp_path: Path) -> None:
    """The interviews guide's commands run against a disposable store.

    Placeholders are substituted from real output as the sequence proceeds, so
    the sequence is executed exactly as a reader would run it.
    """
    env = dict(os.environ)
    env["AGENTIC_ODI_DB"] = str(tmp_path / "interviews.db")
    env["NO_COLOR"] = "1"
    cli = [sys.executable, "-m", "agentic_odi_cli"]

    def run(*args: str) -> str:
        result = _run([*cli, *args], env)
        assert result.returncode == 0, f"{args} failed:\n{result.stdout}{result.stderr}"
        return result.stdout + result.stderr

    run("demo", "load")
    extract = run(
        "candidates",
        "extract",
        "--quote-id",
        "interview-7",
        "--quote",
        "Minimize the time it takes to onboard when a customer signs up. "
        "Minimize the number of setup errors when a customer signs up.",
        "--job-id",
        "demo-job-1",
    )
    candidate_id = _extract_id(r"\(([0-9a-f-]{36})\)", extract)

    run("candidates", "list", "--job-id", "demo-job-1")
    run("candidates", "list", "--status", "proposed", "--json")
    run("candidates", "show", candidate_id)

    accepted = run("candidates", "accept", candidate_id, "--importance", "9", "--satisfaction", "4")
    outcome_id = _extract_id(r"Outcome created:\s*([0-9a-f-]{36})", accepted)

    shown = run("desired-outcomes", "get", outcome_id)
    assert "14.00" in shown  # importance 9 + max(9 - 4, 0)

    # The scoring guide's sequence continues from the same store.
    assert "14.00" in run("score", "8", "2")
    run("summary", "demo-job-1", "--top", "3")
    run("summary", "demo-job-1", "--json")

    # The decision guide renders the brief for the accepted outcome.
    brief = run("brief", outcome_id)
    assert "opportunity_score" in brief
    run("brief", outcome_id, "--json")
