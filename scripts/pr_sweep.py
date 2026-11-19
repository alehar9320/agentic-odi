"""Bucket the open pull request queue, read-only, so it can be worked.

The drain of the open queue (#1040) is 192 pull requests of judgement calls.
Today there is no single view of them, so every pass re-derives the same state
by hand and the result is unauditable. This prints that view: every open pull
request, placed in exactly one bucket, with the facts a disposition needs.

It is a report. It never merges, closes, comments on, or labels anything -- a
tool that mutates the queue cannot be re-run safely while a human works it.

It is offline by default. With no flag it reads a fixtures file, so the unit
test never needs the network; ``--live`` is the only path that shells out to
``gh``, which is the GitHub client the rest of ``scripts/pr_*.py`` already uses.
Under ``--live`` it makes two read-only calls: the open queue, and the merged
numbers the superseded bucket needs.

Run it locally with::

    uv run python scripts/pr_sweep.py --since 30d
    uv run python scripts/pr_sweep.py --since 30d --live --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from doc_churn import parse_window

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_WINDOW = "30d"
DEFAULT_FIXTURES = ROOT / "tests" / "scripts" / "fixtures" / "pr_sweep" / "open_prs.json"

# A pull request with no push or comment for this long is treated as abandoned.
ABANDONED_AFTER = timedelta(days=14)

# Green: GitHub reports the branch merges cleanly into its base.
MERGEABLE = "MERGEABLE"

# The buckets, in report order. ``bucket`` returns exactly one of these.
BUCKETS = (
    "draft",
    "abandoned",
    "stacked",
    "green-superseded",
    "green-mergeable",
    "needs-review",
)

PR_REFERENCE = re.compile(r"#(\d+)")


# ---------------------------------------------------------------------------
# The facts about one open pull request
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OpenPullRequest:
    """One open pull request, as much of it as a disposition needs."""

    number: int
    title: str
    created_at: datetime
    updated_at: datetime
    is_draft: bool
    mergeable: str
    base_ref: str
    head_ref: str
    body: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class SweepContext:
    """What ``bucket`` needs beyond the pull request itself.

    Kept separate so ``bucket`` stays pure: give it a pull request and a
    context, get a bucket name back. No clock, no files, no network.
    """

    now: datetime
    open_heads: frozenset[str] = frozenset()
    merged_numbers: frozenset[int] = frozenset()
    abandoned_after: timedelta = ABANDONED_AFTER


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _parse_time(value: object) -> datetime | None:
    """Parse an ISO-8601 timestamp, tolerating the trailing ``Z`` gh emits.

    ``datetime.fromisoformat`` only accepts a ``Z`` suffix from Python 3.11, and
    this package supports 3.10, so the suffix is normalised by hand.
    """
    if not isinstance(value, str) or not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _file_paths(value: object) -> tuple[str, ...]:
    """The paths a pull request touches, from gh's ``files`` array."""
    if not isinstance(value, list):
        return ()
    paths: list[str] = []
    for entry in value:
        if isinstance(entry, dict) and isinstance(entry.get("path"), str):
            paths.append(entry["path"])
    return tuple(paths)


def parse_payload(payload: object) -> list[OpenPullRequest]:
    """Read a ``gh pr list`` payload into pull requests.

    Malformed rows are skipped rather than fatal: the report is a convenience,
    and one odd row should not hide the rest of the queue.
    """
    if not isinstance(payload, list):
        raise ValueError("expected a JSON array of pull requests")

    pull_requests: list[OpenPullRequest] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        number = row.get("number")
        created_at = _parse_time(row.get("createdAt"))
        updated_at = _parse_time(row.get("updatedAt"))
        if not isinstance(number, int) or created_at is None or updated_at is None:
            continue
        pull_requests.append(
            OpenPullRequest(
                number=number,
                title=row.get("title") if isinstance(row.get("title"), str) else "",
                created_at=created_at,
                updated_at=updated_at,
                is_draft=bool(row.get("isDraft", False)),
                mergeable=row.get("mergeable") if isinstance(row.get("mergeable"), str) else "",
                base_ref=row.get("baseRefName") if isinstance(row.get("baseRefName"), str) else "",
                head_ref=row.get("headRefName") if isinstance(row.get("headRefName"), str) else "",
                body=row.get("body") if isinstance(row.get("body"), str) else "",
                files=_file_paths(row.get("files")),
            )
        )
    return pull_requests


def load_fixtures(path: Path) -> object:
    """Read the offline fixtures file, a saved ``gh pr list`` payload."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_merged_numbers(fixtures_path: Path) -> frozenset[int]:
    """The merged numbers, from the sibling ``merged_prs.json`` if it is there.

    Offline, the superseded bucket needs to know which numbers have merged, and
    the open payload cannot say. The sibling file sits beside ``open_prs.json``;
    when it is absent the set is empty and no pull request is called superseded,
    which is the safe default (better to under-report than to close a live PR).
    """
    merged_path = fixtures_path.parent / "merged_prs.json"
    if not merged_path.exists():
        return frozenset()
    payload = load_fixtures(merged_path)
    if not isinstance(payload, list):
        raise ValueError("expected a JSON array of merged pull requests")
    return frozenset(
        row["number"]
        for row in payload
        if isinstance(row, dict) and isinstance(row.get("number"), int)
    )


def fetch_live(repo: str | None) -> object:
    """Ask ``gh`` for the open pull requests.

    ``headRefName`` and ``body`` are requested beside the fields a table needs
    because the stacked and superseded buckets are decided from them: stacked
    is "base branch is another open pull request's head", superseded is "the
    body names a merged pull request".
    """
    command = [
        "gh",
        "pr",
        "list",
        "--state",
        "open",
        "--limit",
        "1000",
        "--json",
        "number,title,createdAt,updatedAt,isDraft,mergeable,baseRefName,headRefName,body,files",
    ]
    if repo:
        command += ["--repo", repo]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"gh pr list failed: {result.stderr.strip()}")
    return json.loads(result.stdout or "[]")


def fetch_merged_numbers(repo: str | None) -> frozenset[int]:
    """The numbers of merged pull requests, so the superseded bucket can fire.

    The open payload alone cannot say which numbers have merged; this is the
    second and last ``gh`` call, made only under ``--live``.
    """
    command = ["gh", "pr", "list", "--state", "merged", "--limit", "1000", "--json", "number"]
    if repo:
        command += ["--repo", repo]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"gh pr list --state merged failed: {result.stderr.strip()}")
    payload = json.loads(result.stdout or "[]")
    if not isinstance(payload, list):
        raise ValueError("expected a JSON array of merged pull requests")
    return frozenset(
        row["number"]
        for row in payload
        if isinstance(row, dict) and isinstance(row.get("number"), int)
    )


def filter_since(pull_requests: list[OpenPullRequest], cutoff: datetime) -> list[OpenPullRequest]:
    """Keep the pull requests created at or after ``cutoff``."""
    return [pr for pr in pull_requests if pr.created_at >= cutoff]


# ---------------------------------------------------------------------------
# The bucket
# ---------------------------------------------------------------------------


def _is_abandoned(pr: OpenPullRequest, context: SweepContext) -> bool:
    """No push and no comment for longer than the abandonment window."""
    return context.now - pr.updated_at > context.abandoned_after


def _is_stacked(pr: OpenPullRequest, context: SweepContext) -> bool:
    """The base branch is another open pull request's head."""
    return pr.base_ref != pr.head_ref and pr.base_ref in context.open_heads


def _is_superseded(pr: OpenPullRequest, context: SweepContext) -> bool:
    """The body names a pull request that has already merged."""
    return any(int(ref) in context.merged_numbers for ref in PR_REFERENCE.findall(pr.body))


def bucket(pr: OpenPullRequest, context: SweepContext) -> str:
    """The single bucket this pull request belongs to.

    Precedence, first match wins, so the disposition that needs no judgement
    outranks the ones that do:

    * ``draft`` -- an open draft is not yet a review candidate.
    * ``abandoned`` -- no activity past the window; close or revive.
    * ``stacked`` -- the base is another open pull request's head; merge
      root-first, or re-cut. This outranks the superseded check, matching the
      stacked-chain runbook in #1040.
    * ``green-superseded`` -- the body names a merged pull request; close it.
    * ``green-mergeable`` -- green and nothing above applies; merge it.
    * ``needs-review`` -- everything else, e.g. a conflict, or ``UNKNOWN``.
    """
    if pr.is_draft:
        return "draft"
    if _is_abandoned(pr, context):
        return "abandoned"
    if _is_stacked(pr, context):
        return "stacked"
    if _is_superseded(pr, context):
        return "green-superseded"
    if pr.mergeable == MERGEABLE:
        return "green-mergeable"
    return "needs-review"


def bucket_all(
    pull_requests: list[OpenPullRequest], context: SweepContext
) -> dict[str, list[OpenPullRequest]]:
    """Place every pull request in its bucket, each list ordered by number."""
    grouped: dict[str, list[OpenPullRequest]] = {name: [] for name in BUCKETS}
    for pr in pull_requests:
        grouped[bucket(pr, context)].append(pr)
    for rows in grouped.values():
        rows.sort(key=lambda pr: pr.number)
    return grouped


def context_for(
    pull_requests: list[OpenPullRequest],
    now: datetime,
    merged_numbers: frozenset[int] = frozenset(),
) -> SweepContext:
    """Build the context the buckets need from the queue itself."""
    return SweepContext(
        now=now,
        open_heads=frozenset(pr.head_ref for pr in pull_requests if pr.head_ref),
        merged_numbers=merged_numbers,
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _age(pr: OpenPullRequest, now: datetime) -> str:
    days = max((now - pr.created_at).days, 0)
    return f"{days}d"


def render_bucket(name: str, rows: list[OpenPullRequest], now: datetime) -> str:
    """One bucket as the table a person reads."""
    lines = [f"## {name} ({len(rows)})", ""]
    if not rows:
        lines.append("_none_")
        return "\n".join(lines)
    lines.append("| PR | Age | Draft | Mergeable | Last push | Files |")
    lines.append("|---|---|---|---|---|---|")
    for pr in rows:
        lines.append(
            f"| #{pr.number} | {_age(pr, now)} | {'yes' if pr.is_draft else 'no'} "
            f"| {pr.mergeable or 'UNKNOWN'} | {pr.updated_at.date().isoformat()} "
            f"| {len(pr.files)} |"
        )
    return "\n".join(lines)


def render_table(
    grouped: dict[str, list[OpenPullRequest]], total: int, window: str, now: datetime
) -> str:
    """Every bucket, in order, with the count of open pull requests."""
    lines = [f"{total} open pull request(s) within --since {window}", ""]
    for name in BUCKETS:
        lines.append(render_bucket(name, grouped[name], now))
        lines.append("")
    return "\n".join(lines).rstrip()


def render_json(
    grouped: dict[str, list[OpenPullRequest]], total: int, window: str, now: datetime
) -> str:
    """The machine-readable report, for a caller that wants to diff two runs.

    Deliberately carries no wall-clock stamp: two runs of the same queue on the
    same day produce byte-identical output, which is what makes a diff between
    two sweeps meaningful. ``last_push`` is a date, so it is stable too.
    """
    payload = {
        "window": window,
        "total_pull_requests": total,
        "counts": {name: len(grouped[name]) for name in BUCKETS},
        "buckets": {
            name: [
                {
                    "number": pr.number,
                    "title": pr.title,
                    "age_days": max((now - pr.created_at).days, 0),
                    "is_draft": pr.is_draft,
                    "mergeable": pr.mergeable or "UNKNOWN",
                    "last_push": pr.updated_at.date().isoformat(),
                    "files_touched": len(pr.files),
                }
                for pr in grouped[name]
            ]
            for name in BUCKETS
        },
    }
    return json.dumps(payload, indent=2, sort_keys=False)


# ---------------------------------------------------------------------------
# The command line
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since",
        default=DEFAULT_WINDOW,
        metavar="Nd",
        help=f"window of creation dates to report over, e.g. 30d (default: {DEFAULT_WINDOW})",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="read the real queue with gh instead of the offline fixtures file",
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

    now = datetime.now(timezone.utc)
    try:
        if args.live:
            payload = fetch_live(args.repo)
            merged_numbers = fetch_merged_numbers(args.repo)
        else:
            payload = load_fixtures(args.fixtures)
            merged_numbers = load_merged_numbers(args.fixtures)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"could not read open pull requests: {error}", file=sys.stderr)
        return 1

    try:
        pull_requests = filter_since(parse_payload(payload), now - window)
    except ValueError as error:
        print(f"could not read open pull requests: {error}", file=sys.stderr)
        return 1

    grouped = bucket_all(pull_requests, context_for(pull_requests, now, merged_numbers))
    if args.json:
        print(render_json(grouped, len(pull_requests), args.since, now))
    else:
        print(render_table(grouped, len(pull_requests), args.since, now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
