"""Keep the Python coverage floor from being lowered (issue #88).

The floor lives in ``pyproject.toml`` and is enforced by pytest's exit code.
CI compares it against the base branch and refuses a change that lowers it.

Run locally with ``uv run python scripts/coverage_floor.py``. In CI, pass the
pull request's base ref:

    uv run python scripts/coverage_floor.py --base origin/main
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
FAIL_UNDER = re.compile(r"^fail_under\s*=\s*(\d+(?:\.\d+)?)\s*$", re.MULTILINE)


def floor_from_toml(text: str) -> float:
    match = FAIL_UNDER.search(text)
    if match is None:
        raise ValueError("no fail_under setting in [tool.coverage.report]")
    return float(match.group(1))


def compare(*, head: float, base: float) -> str | None:
    """The error message when the floor went down, or ``None`` when it did not."""
    if head < base:
        return f"the coverage floor may not be lowered: {head:g}% < {base:g}%"
    return None


def base_floor(ref: str) -> float:
    shown = subprocess.run(
        ["git", "show", f"{ref}:pyproject.toml"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return floor_from_toml(shown.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", help="the base ref to compare against, e.g. origin/main")
    args = parser.parse_args(argv)

    head = floor_from_toml(PYPROJECT.read_text(encoding="utf-8"))
    if args.base:
        error = compare(head=head, base=base_floor(args.base))
        if error is not None:
            print(error, file=sys.stderr)
            return 1
    print(f"coverage floor: {head:g}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
