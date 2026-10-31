"""Execute the ninety-second tour and regenerate its committed artifacts.

Every command in ``docs/tour/script.md`` is executed here against a disposable
store, so a command that cannot run fails the build with the step named rather
than being described in prose that rots. The output is written as an
asciinema-format cast and a generated ``docs/tour/README.md`` transcript.

Determinism: the run uses a fresh temporary store, so the store path and any
generated UUID are replaced with stable placeholders. That normalization is
narrow on purpose — it hides an identifier, not a meaningful difference in the
output. Two runs of the same build produce byte-identical artifacts.

Usage::

    uv run python scripts/tour.py            # regenerate and check the budget
    uv run python scripts/tour.py --check    # verify committed files match
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess  # nosec B404 - fixed argv, no shell (see B603 note)
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_MD = REPO_ROOT / "docs" / "tour" / "script.md"
CAST_PATH = REPO_ROOT / "docs" / "tour" / "tour.cast"
README_PATH = REPO_ROOT / "docs" / "tour" / "README.md"

# The walkthrough budget, measured on the wall clock (narrated/capture time, not
# installation time).
BUDGET_SECONDS = 90.0

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_COMMAND = re.compile(r"^\d+\.\s+`([^`]+)`\s+—\s+(.*)$")


class TourError(RuntimeError):
    """A tour step could not run; the message names the step."""


def read_steps() -> list[tuple[str, str]]:
    """Parse the ordered command list from ``script.md``.

    The prose is the source of truth: a command removed from the script is a
    command the tour no longer runs, which is the point.
    """
    steps: list[tuple[str, str]] = []
    for line in SCRIPT_MD.read_text(encoding="utf-8").splitlines():
        match = _COMMAND.match(line.strip())
        if match:
            steps.append((match.group(1), match.group(2).strip()))
    if not steps:
        raise TourError(f"no numbered commands found in {SCRIPT_MD}")
    return steps


def _run(argv: list[str], env: dict[str, str]) -> str:
    result = subprocess.run(  # nosec B603 - fixed argv list, no shell
        argv,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise TourError(f"step failed ({' '.join(argv[3:])}):\n{result.stdout}{result.stderr}")
    return result.stdout + result.stderr


def _cli_args(command: str) -> list[str]:
    """Turn a documented ``agentic-odi …`` line into a runnable argv list."""
    if not command.startswith("agentic-odi "):
        raise TourError(f"command is not an agentic-odi invocation: {command!r}")
    return shlex.split(command[len("agentic-odi ") :])


def _resolve(command: str, substitutions: dict[str, str], step_index: int) -> str:
    for key, value in substitutions.items():
        command = command.replace("{" + key + "}", value)
    if "{" in command:
        raise TourError(f"step {step_index} has an unresolved substitution: {command!r}")
    return command


class _Normalizer:
    """Replace run-specific identifiers with stable placeholders."""

    def __init__(self, store_path: str) -> None:
        self._store_path = store_path
        self._ids: dict[str, str] = {}

    def text(self, raw: str) -> str:
        raw = raw.replace(self._store_path, "<store>")

        def _swap(match: re.Match[str]) -> str:
            found = match.group(0)
            token = self._ids.setdefault(found, f"<id-{len(self._ids) + 1}>")
            return token

        return _UUID.sub(_swap, raw)


def _extract_candidate_id(output: str) -> str:
    match = re.search(r"\((" + _UUID.pattern + r")\)", output)
    if not match:
        raise TourError(f"no candidate id in extract output:\n{output}")
    return match.group(1)


def _extract_outcome_id(output: str) -> str:
    match = re.search(r"Outcome created:\s*(" + _UUID.pattern + r")", output)
    if not match:
        raise TourError(f"no outcome id in accept output:\n{output}")
    return match.group(1)


def run_tour() -> tuple[float, list[tuple[str, str]], list[str]]:
    """Run every documented step; return (seconds, transcript, cast events)."""
    steps = read_steps()
    tmp_dir = tempfile.mkdtemp(prefix="odi-tour-")
    store_path = str(Path(tmp_dir) / "tour.db")
    env = dict(os.environ)
    env["AGENTIC_ODI_DB"] = store_path
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"

    normalizer = _Normalizer(store_path)
    substitutions: dict[str, str] = {}
    transcript: list[tuple[str, str]] = []
    events: list[str] = []
    elapsed = 0.0

    for index, (command, explanation) in enumerate(steps, start=1):
        resolved = _resolve(command, substitutions, index)
        prompt = f"$ {command}\n"
        events.append(prompt)

        started = time.monotonic()
        try:
            output = _run([sys.executable, "-m", "agentic_odi_cli", *_cli_args(resolved)], env)
        except TourError as exc:
            raise TourError(f"step {index} ({command}): {exc}") from exc
        elapsed += time.monotonic() - started

        if "candidates extract" in command:
            substitutions["candidate_id"] = _extract_candidate_id(output)
        if "candidates accept" in command:
            substitutions["outcome_id"] = _extract_outcome_id(output)

        # Resolve a substitution the moment its source step has run, so the
        # transcript shows the real id it used.
        normalized = normalizer.text(output)
        events.append(normalized)
        transcript.append((command, explanation))
        transcript.append((normalized, ""))

    if elapsed > BUDGET_SECONDS:
        raise TourError(f"the tour took {elapsed:.1f}s, over the {BUDGET_SECONDS:.0f}s budget")
    return elapsed, transcript, events


def _cast_bytes(events: list[str]) -> str:
    """Serialize the transcript as an asciinema v2 cast.

    Pacing is a fixed step per event rather than the measured wall-clock: the
    committed cast must be byte-identical across runs, and a real timestamp is
    run-specific noise. The measured duration is reported by the build, not
    embedded here.
    """
    header = {
        "version": 2,
        "width": 100,
        "height": 40,
        "timestamp": 0,
        "env": {"SHELL": "/bin/sh", "TERM": "dumb"},
    }
    lines = [json.dumps(header, sort_keys=True)]
    for index, text in enumerate(events):
        lines.append(json.dumps([round(index * 0.5, 3), "o", text]))
    return "\n".join(lines) + "\n"


def _readme_bytes(transcript: list[tuple[str, str]]) -> str:
    out = [
        "<!-- Generated by scripts/tour.py. Do not edit by hand. -->",
        "",
        "# The ninety-second tour",
        "",
        "A generated transcript of `docs/tour/script.md`, run offline against a",
        f"disposable sample store. The walkthrough is measured against the {BUDGET_SECONDS:.0f}s",
        "budget by `tests/test_tour.py`, which fails if it is exceeded; the measured",
        "time is reported by `uv run python scripts/tour.py` (capture time; setup and",
        "install are not counted).",
        "",
        "Regenerate with `uv run python scripts/tour.py`. The cast is committed at",
        "`docs/tour/tour.cast`.",
        "",
        "```console",
    ]
    for line, _explanation in transcript:
        out.append(line.rstrip("\n"))
    out.append("```")
    out.append("")
    return "\n".join(out) + "\n"


def build() -> tuple[str, str, float]:
    seconds, transcript, events = run_tour()
    return _cast_bytes(events), _readme_bytes(transcript), seconds


def main(argv: list[str]) -> int:
    check = "--check" in argv
    cast, readme, seconds = build()
    if check:
        current_cast = CAST_PATH.read_text(encoding="utf-8") if CAST_PATH.exists() else ""
        current_readme = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""
        if current_cast != cast or current_readme != readme:
            print(
                "tour artifacts are stale; run `uv run python scripts/tour.py`",
                file=sys.stderr,
            )
            return 1
        print(f"tour artifacts are current ({seconds:.1f}s of {BUDGET_SECONDS:.0f}s)")
        return 0
    CAST_PATH.write_text(cast, encoding="utf-8")
    README_PATH.write_text(readme, encoding="utf-8")
    print(f"wrote {CAST_PATH.relative_to(REPO_ROOT)} and {README_PATH.relative_to(REPO_ROOT)}")
    print(f"measured walkthrough: {seconds:.1f}s of {BUDGET_SECONDS:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
