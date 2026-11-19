"""Rank the files merged pull requests touch, so conflicts are measurable.

The repository carries a ``merge-conflict`` label but no instrument for the
churn that produces conflicts: which files, and which directories, appear in
the most merged pull requests. This prints that ranking.

It is offline by default. With no flag it reads a fixtures file, so the unit
test never needs the network; ``--live`` is the only path that shells out to
``gh``, which is the GitHub client the rest of ``scripts/pr_*.py`` already uses.

Run it locally with::

    uv run python scripts/doc_churn.py --since 30d
    uv run python scripts/doc_churn.py --since 30d --live --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WINDOW = "30d"
DEFAULT_TOP = 20
DEFAULT_FIXTURES = ROOT / "tests" / "scripts" / "fixtures" / "doc_churn" / "merged_prs.json"

WINDOW = re.compile(r"^(\d+)d$")


def parse_window(text: str) -> timedelta:
    """Parse a ``<n>d`` window such as ``30d`` into a duration."""
    match = WINDOW.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"window must look like '30d', got {text!r}")
    days = int(match.group(1))
    if days <= 0:
        raise ValueError(f"window must be at least one day, got {text!r}")
    return timedelta(days=days)


def _merged_at(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, tolerating the trailing ``Z`` gh emits.

    ``datetime.fromisoformat`` only accepts a ``Z`` suffix from Python 3.11, and
    this package supports 3.10, so the suffix is normalised by hand.
    """
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass(frozen=True)
class MergedPullRequest:
    """One merged pull request: its number, merge time, and touched paths."""

    number: int
    merged_at: datetime
    files: tuple[str, ...]


def parse_payload(payload: object) -> list[MergedPullRequest]:
    """Parse ``gh pr list --json number,mergedAt,files`` output.

    ``files`` arrives as a list of ``{"path": ...}`` objects. A malformed entry
    is skipped rather than raising, because a report must not die on one odd
    row from the API.
    """
    if not isinstance(payload, list):
        raise ValueError("expected a JSON array of pull requests")
    pull_requests: list[MergedPullRequest] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        number = entry.get("number")
        merged_at = entry.get("mergedAt")
        if not isinstance(number, int) or not isinstance(merged_at, str) or not merged_at:
            continue
        files: list[str] = []
        for item in entry.get("files") or []:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                files.append(item["path"])
            elif isinstance(item, str):
                files.append(item)
        pull_requests.append(
            MergedPullRequest(number=number, merged_at=_merged_at(merged_at), files=tuple(files))
        )
    return pull_requests


def filter_since(
    pull_requests: list[MergedPullRequest], cutoff: datetime
) -> list[MergedPullRequest]:
    """Keep the pull requests merged at or after ``cutoff``."""
    return [pr for pr in pull_requests if pr.merged_at >= cutoff]


def file_counts(pull_requests: list[MergedPullRequest]) -> Counter[str]:
    """Count, per path, how many pull requests touched it.

    A path repeated inside one pull request counts once: the number is "how many
    pull requests touched this file", not "how many file entries named it".
    """
    counts: Counter[str] = Counter()
    for pr in pull_requests:
        for path in set(pr.files):
            counts[path] += 1
    return counts


def directory_of(path: str) -> str:
    """The top-level directory of a path; a root-level file is its own."""
    head, separator, _tail = path.partition("/")
    return head if separator else path


def directory_counts(pull_requests: list[MergedPullRequest]) -> Counter[str]:
    """Count, per top-level directory, how many pull requests touched it."""
    counts: Counter[str] = Counter()
    for pr in pull_requests:
        for directory in {directory_of(path) for path in pr.files}:
            counts[directory] += 1
    return counts


def rank(counts: Counter[str], total: int, top: int) -> list[tuple[str, int, float]]:
    """``(name, pull_requests, share)`` for the ``top`` busiest entries.

    Ties break on the name so two runs over the same data print the same order.
    """
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [(name, count, (count / total if total else 0.0)) for name, count in ranked[:top]]


def render_table(rows: list[tuple[str, int, float]], total: int) -> str:
    """The ranked table a person reads, with the share of pull requests."""
    lines = [
        f"{total} merged pull request(s) in the window",
        "",
        "| # | Path | PRs | Share |",
        "|---|---|---|---|",
    ]
    for position, (name, count, share) in enumerate(rows, start=1):
        lines.append(f"| {position} | `{name}` | {count} | {share:.0%} |")
    return "\n".join(lines)


def render_json(
    rows: list[tuple[str, int, float]],
    directories: list[tuple[str, int, float]],
    total: int,
    window: str,
) -> str:
    """The machine-readable report, for a caller that wants to diff two runs."""
    payload = {
        "window": window,
        "total_pull_requests": total,
        "files": [
            {"path": name, "pull_requests": count, "share": round(share, 4)}
            for name, count, share in rows
        ],
        "directories": [
            {"directory": name, "pull_requests": count, "share": round(share, 4)}
            for name, count, share in directories
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=False)


def load_fixtures(path: Path) -> object:
    """Read the offline fixtures file, a saved ``gh pr list`` payload."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def fetch_live(repo: str | None, cutoff: datetime) -> object:
    """Ask ``gh`` for merged pull requests merged at or after ``cutoff``.

    ``gh pr list`` has no ``--paginate``; ``--limit`` is the only page size and
    it fetches every page up to that count internally, so one call is enough.
    """
    command = [
        "gh",
        "pr",
        "list",
        "--state",
        "merged",
        "--limit",
        "1000",
        "--search",
        f"merged:>={cutoff.date().isoformat()}",
        "--json",
        "number,mergedAt,files",
    ]
    if repo:
        command += ["--repo", repo]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"gh pr list failed: {result.stderr.strip()}")
    return json.loads(result.stdout or "[]")


def build_report(
    payload: object, cutoff: datetime, top: int
) -> tuple[list[tuple[str, int, float]], list[tuple[str, int, float]], int]:
    """``(file rows, directory rows, total)`` for a payload and a cutoff."""
    pull_requests = filter_since(parse_payload(payload), cutoff)
    total = len(pull_requests)
    return (
        rank(file_counts(pull_requests), total, top),
        rank(directory_counts(pull_requests), total, top),
        total,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since",
        default=DEFAULT_WINDOW,
        metavar="Nd",
        help=f"window to report over, e.g. 30d (default: {DEFAULT_WINDOW})",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP,
        help=f"how many rows to print (default: {DEFAULT_TOP})",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="read the real history with gh instead of the offline fixtures file",
    )
    parser.add_argument(
        "--repo",
        help="owner/repo for --live; defaults to the checkout's remote",
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FIXTURES,
        help="fixtures file for the offline default",
    )
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    try:
        window = parse_window(args.since)
    except ValueError as error:
        print(f"invalid --since: {error}", file=sys.stderr)
        return 2

    cutoff = datetime.now(timezone.utc) - window
    try:
        payload = fetch_live(args.repo, cutoff) if args.live else load_fixtures(args.fixtures)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"could not read merged pull requests: {error}", file=sys.stderr)
        return 1

    try:
        files, directories, total = build_report(payload, cutoff, args.top)
    except ValueError as error:
        print(f"could not read merged pull requests: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(render_json(files, directories, total, args.since))
    else:
        print(render_table(files, total))
        print()
        print("By directory:")
        print(render_table(directories, total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
