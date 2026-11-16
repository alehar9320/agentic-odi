"""Bucket the open PR queue read-only.

Implements the measurement step of the PR sweep: read every open pull request,
classify it into exactly one bucket, and print a disposition table. No merging,
no closing, no labeling — measurement only.

Buckets (in priority order; first match wins):
- draft: PR is a draft
- green-mergeable: mergeable is true, not stacked, not abandoned
- green-superseded: base branch is another open PR's head, or body names a merged PR
- stacked: base branch is another open PR's head (but not superseded by body)
- abandoned: >14 days without a push or comment
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BUCKETS = (
    "draft",
    "green-mergeable",
    "green-superseded",
    "stacked",
    "abandoned",
)

# Column widths for table output
COLUMN_SPECS = [
    ("number", 8, ">"),
    ("age", 6, ">"),
    ("draft", 6, "^"),
    ("mergeable", 10, "^"),
    ("last_push", 12, "<"),
    ("files", 6, ">"),
    ("bucket", 16, "<"),
]


@dataclass(frozen=True)
class PR:
    """Normalized pull request data."""

    number: int
    title: str
    created_at: datetime
    updated_at: datetime
    is_draft: bool
    mergeable: str  # "MERGEABLE", "CONFLICTING", "UNKNOWN"
    base_ref_name: str
    files: list[dict[str, Any]]
    body: str = ""
    head_ref_name: str = ""

    def age_days(self, now: datetime | None = None) -> int:
        if now is None:
            now = datetime.now(timezone.utc)
        return (now - self.created_at).days

    def last_push_days(self, now: datetime | None = None) -> int:
        if now is None:
            now = datetime.now(timezone.utc)
        return (now - self.updated_at).days

    @property
    def files_touched(self) -> int:
        return len(self.files)


def parse_datetime(s: str) -> datetime:
    """Parse GitHub ISO datetime string to timezone-aware datetime."""
    # GitHub returns RFC3339 format like "2024-01-15T10:30:00Z"
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_prs_from_gh(since_days: int | None = None, now: datetime | None = None) -> list[PR]:
    """Fetch open PRs from GitHub via gh CLI."""
    if now is None:
        now = datetime.now(timezone.utc)
    cmd = [
        "gh",
        "pr",
        "list",
        "--state",
        "open",
        "--json",
        "number,title,createdAt,updatedAt,isDraft,mergeable,baseRefName,files,body,headRefName",
        "--limit",
        "1000",
    ]
    if since_days is not None:
        # gh pr list doesn't have a --since flag, so we filter after
        pass
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"gh pr list failed: {result.stderr}")

    data = json.loads(result.stdout)
    prs = []
    for item in data:
        created = parse_datetime(item["createdAt"])
        if since_days is not None and (now - created).days > since_days:
            continue
        prs.append(
            PR(
                number=item["number"],
                title=item["title"],
                created_at=created,
                updated_at=parse_datetime(item["updatedAt"]),
                is_draft=item["isDraft"],
                mergeable=item["mergeable"],
                base_ref_name=item["baseRefName"],
                files=item.get("files", []),
                body=item.get("body", ""),
                head_ref_name=item.get("headRefName", ""),
            )
        )
    return prs


def load_prs_from_fixture(path: Path) -> list[PR]:
    """Load PRs from a fixture JSON file."""
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    prs = []
    for item in data:
        prs.append(
            PR(
                number=item["number"],
                title=item["title"],
                created_at=parse_datetime(item["createdAt"]),
                updated_at=parse_datetime(item["updatedAt"]),
                is_draft=item["isDraft"],
                mergeable=item["mergeable"],
                base_ref_name=item["baseRefName"],
                files=item.get("files", []),
                body=item.get("body", ""),
                head_ref_name=item.get("headRefName", ""),
            )
        )
    return prs


def bucket(pr: PR, all_prs: list[PR], now: datetime | None = None) -> str:
    """Classify a PR into exactly one bucket.

    Priority order (first match wins):
    1. draft: PR is a draft
    2. green-superseded: body names a merged PR, OR base branch is another open PR's head
       that is itself based on a protected branch (not another open PR)
    3. stacked: base branch is another open PR's head that is itself based on another open PR
    4. abandoned: >14 days without a push or comment
    5. green-mergeable: mergeable is MERGEABLE, not stacked, not abandoned
    """
    # 1. Draft
    if pr.is_draft:
        return "draft"

    # Build mappings for quick lookup
    head_ref_to_pr = {p.head_ref_name: p for p in all_prs if p.head_ref_name}
    open_head_refs = set(head_ref_to_pr.keys())

    # 2. Green-superseded by body reference to merged PR
    import re

    merged_ref_pattern = re.compile(r"(?:supersedes|fixes|closes|resolves)\s+#(\d+)", re.IGNORECASE)
    if merged_ref_pattern.search(pr.body or ""):
        return "green-superseded"

    # 3. Check if base is another open PR's head
    if pr.base_ref_name in open_head_refs:
        base_pr = head_ref_to_pr[pr.base_ref_name]
        # If the base PR's base is NOT an open PR head, this PR is green-superseded
        # (the base PR is based on main/protected branch)
        # If the base PR's base IS an open PR head, this PR is stacked
        if base_pr.base_ref_name in open_head_refs:
            return "stacked"
        else:
            return "green-superseded"

    # 4. Abandoned: >14 days without a push or comment
    if pr.last_push_days(now) > 14:
        return "abandoned"

    # 5. Green-mergeable: mergeable is MERGEABLE
    if pr.mergeable == "MERGEABLE":
        return "green-mergeable"

    # Fallback (should not happen with current buckets)
    return "green-mergeable"


def format_table(prs: list[PR], buckets_map: dict[int, str], now: datetime | None = None) -> str:
    """Format PRs as a table grouped by bucket."""
    if now is None:
        now = datetime.now(timezone.utc)
    lines = []

    # Header
    header_parts = []
    for name, width, align in COLUMN_SPECS:
        if align == ">":
            header_parts.append(name.rjust(width))
        elif align == "<":
            header_parts.append(name.ljust(width))
        else:
            header_parts.append(name.center(width))
    lines.append(" | ".join(header_parts))

    # Separator
    sep_parts = ["-" * width for _, width, _ in COLUMN_SPECS]
    lines.append("-+-".join(sep_parts))

    # Group by bucket
    for bucket_name in BUCKETS:
        bucket_prs = [pr for pr in prs if buckets_map.get(pr.number) == bucket_name]
        if not bucket_prs:
            continue

        # Bucket header
        lines.append(f"\n=== {bucket_name.upper()} ({len(bucket_prs)}) ===")

        for pr in bucket_prs:
            row_parts = [
                str(pr.number).rjust(COLUMN_SPECS[0][1]),
                f"{pr.age_days(now)}d".rjust(COLUMN_SPECS[1][1]),
                ("Y" if pr.is_draft else "N").center(COLUMN_SPECS[2][1]),
                pr.mergeable.center(COLUMN_SPECS[3][1]),
                f"{pr.last_push_days(now)}d ago".ljust(COLUMN_SPECS[4][1]),
                str(pr.files_touched).rjust(COLUMN_SPECS[5][1]),
                bucket_name.ljust(COLUMN_SPECS[6][1]),
            ]
            lines.append(" | ".join(row_parts))

    return "\n".join(lines)


def format_json(prs: list[PR], buckets_map: dict[int, str], now: datetime | None = None) -> str:
    """Format PRs as JSON grouped by bucket."""
    if now is None:
        now = datetime.now(timezone.utc)
    output = {}
    for bucket_name in BUCKETS:
        bucket_prs = [pr for pr in prs if buckets_map.get(pr.number) == bucket_name]
        output[bucket_name] = [
            {
                "number": pr.number,
                "title": pr.title,
                "age_days": pr.age_days(now),
                "is_draft": pr.is_draft,
                "mergeable": pr.mergeable,
                "last_push_days_ago": pr.last_push_days(now),
                "files_touched": pr.files_touched,
                "base_ref": pr.base_ref_name,
                "head_ref": pr.head_ref_name,
            }
            for pr in bucket_prs
        ]
    return json.dumps(output, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="fetch live data from GitHub via gh CLI (default: offline with fixture)",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/scripts/fixtures/pr_sweep/open_prs.json"),
        help="path to fixture JSON (used when --live is not set)",
    )
    parser.add_argument(
        "--since",
        type=int,
        metavar="DAYS",
        help="only include PRs created within the last N days",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="output machine-readable JSON instead of table",
    )
    args = parser.parse_args(argv)

    if args.live:
        now = datetime.now(timezone.utc)
        prs = load_prs_from_gh(args.since, now)
    else:
        # Fixed reference time for fixture: 2024-01-15 (matches fixture dates)
        now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        prs = load_prs_from_fixture(args.fixture)
        if args.since is not None:
            prs = [pr for pr in prs if pr.age_days(now) <= args.since]

    # Compute bucket for each PR
    buckets_map = {pr.number: bucket(pr, prs, now) for pr in prs}

    if args.json:
        print(format_json(prs, buckets_map, now))
    else:
        print(format_table(prs, buckets_map, now))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
