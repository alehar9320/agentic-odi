"""Compute the labels a reviewer should see on a pull request.

Every function here is pure: give it facts about a pull request, get labels
back. The workflow gathers the facts with ``gh``; this module never touches the
network, so its behaviour can be pinned by tests.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from pr_provenance import classify

# Agents declare their own metadata in an HTML comment. The body may be
# multi-line, so the pattern spans lines and captures everything up to the
# closing marker.
AGENT_METADATA_PATTERN = re.compile(
    r"<!--\s*AGENT_METADATA\s*(.*?)\s*-->",
    re.DOTALL,
)

# Size ladder. A reviewer reads this as "how much do I have to read".
SIZE_THRESHOLDS: tuple[tuple[int, str], ...] = (
    (50, "size/XS"),
    (250, "size/S"),
    (800, "size/M"),
    (2000, "size/L"),
)
LARGEST_SIZE_LABEL = "size/XL"

# Manifests and lockfiles. A change here can alter the build for everyone, so it
# is worth a reviewer's attention even when the diff is one line.
DEPENDENCY_FILES: frozenset[str] = frozenset(
    {
        "Cargo.lock",
        "Cargo.toml",
        "go.mod",
        "go.sum",
        "package-lock.json",
        "package.json",
        "pnpm-lock.yaml",
        "pyproject.toml",
        "requirements.txt",
        "uv.lock",
        "yarn.lock",
    }
)

DEPENDENCY_LABEL = "dependencies"

# Top-level directory -> label. Matching on the first path segment keeps
# ``apps/studio-api`` from being read as ``apps/studio``.
DOMAIN_DIRECTORIES: dict[str, str] = {
    "apps/cli": "area/cli",
    "apps/mcp-server": "area/mcp",
    "apps/studio": "area/studio",
    "apps/studio-api": "area/studio",
    "brand": "area/brand",
    "infra": "area/infra",
    "packages/connectors": "area/connectors",
    "packages/core": "area/core",
    "packaging": "area/release",
    "scripts": "area/release",
    "website": "area/website",
}

# Files matched by exact path rather than by directory.
DOMAIN_FILES: dict[str, str] = {
    "wrangler.jsonc": "area/infra",
    "release-please-config.json": "area/release",
    ".release-please-manifest.json": "area/release",
}

DOMAIN_PREFIXES: tuple[tuple[str, str], ...] = (
    (".github/", "area/ci"),
    ("docs/", "area/docs"),
)

PROVENANCE_LABELS: frozenset[str] = frozenset({"🤖 agent", "👤 human"})
TELEMETRY_LABELS: frozenset[str] = frozenset(
    {"breaking change", "needs deep dive", "telemetry invalid"}
)
SIZE_LABELS: frozenset[str] = frozenset({"size/XS", "size/S", "size/M", "size/L", "size/XL"})
DOMAIN_LABELS: frozenset[str] = frozenset(
    set(DOMAIN_DIRECTORIES.values()) | set(DOMAIN_FILES.values()) | {"area/ci", "area/docs"}
)

# Every label this system may add or remove. It deliberately excludes the risk
# tiers and the merge-state labels: those belong to the risk scorer and to the
# merge-conflict workflow, and removing them here would fight those jobs.
MANAGED_LABELS: frozenset[str] = (
    PROVENANCE_LABELS | SIZE_LABELS | DOMAIN_LABELS | TELEMETRY_LABELS | {DEPENDENCY_LABEL}
)


def size_label(additions: int, deletions: int) -> str:
    """Classify a diff by total lines changed."""
    total = max(additions, 0) + max(deletions, 0)
    for ceiling, label in SIZE_THRESHOLDS:
        if total < ceiling:
            return label
    return LARGEST_SIZE_LABEL


def domain_labels(filenames: list[str]) -> set[str]:
    """Map changed paths to the components they touch."""
    labels: set[str] = set()
    for filename in filenames or []:
        path = filename.replace("\\", "/")
        # Strip only a genuine leading "./"; lstrip("./") would also eat the dot
        # in a real dotfile like .github/workflows/ci.yml.
        if path.startswith("./"):
            path = path[2:]
        for prefix, label in DOMAIN_PREFIXES:
            if path.startswith(prefix):
                labels.add(label)
        if path.endswith(".md"):
            labels.add("area/docs")
        if path in DOMAIN_FILES:
            labels.add(DOMAIN_FILES[path])
        # Longest directory match wins, so apps/studio-api is matched by its own
        # entry rather than falling through to apps/studio. Both map to
        # area/studio today, but the ordering keeps that from being load-bearing.
        for directory in sorted(DOMAIN_DIRECTORIES, key=len, reverse=True):
            if path == directory or path.startswith(f"{directory}/"):
                labels.add(DOMAIN_DIRECTORIES[directory])
                break
    return labels


def is_dependency_change(filenames: list[str]) -> bool:
    """True when any changed file is a dependency manifest or lockfile."""
    return any(
        filename.replace("\\", "/").rsplit("/", 1)[-1] in DEPENDENCY_FILES
        for filename in filenames or []
    )


def telemetry_labels(body: str | None) -> set[str]:
    """Read the agent's own metadata block out of a pull request body.

    Agents embed a JSON object in an HTML comment. An unreadable block is worth
    saying out loud rather than ignoring, so it gets its own label; a body with
    no block at all is perfectly normal and gets nothing.
    """
    match = AGENT_METADATA_PATTERN.search(body or "")
    if match is None:
        return set()

    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {"telemetry invalid"}

    if not isinstance(payload, dict):
        return {"telemetry invalid"}

    labels: set[str] = set()
    # ``is True`` rather than a truthiness test: a string "false" or the integer
    # 1 is not the boolean the contract asks for, and guessing would put a
    # breaking-change label on a PR that never claimed one.
    if payload.get("has_breaking_changes") is True:
        labels.add("breaking change")
    if payload.get("agent_confidence") == "low":
        labels.add("needs deep dive")
    return labels


def _pages(payload: object) -> list:
    """Flatten ``gh api --paginate --slurp`` output into one list of records.

    ``--paginate`` wraps each page in its own array, so a 150-commit PR arrives
    as ``[[...100...], [...50...]]``. Treating that as one flat list would read
    only the first page and quietly under-count the diff. A single page may also
    arrive flat, so both shapes are accepted.
    """
    if not isinstance(payload, list):
        return []
    if payload and all(isinstance(page, list) for page in payload):
        return [record for page in payload for record in page]
    return payload


def build_facts(
    meta: dict | None,
    commits_payload: object,
    files_payload: object,
) -> dict:
    """Assemble the fact sheet ``compute_labels`` reads, from GitHub payloads."""
    meta = meta or {}
    author = dict(meta.get("author") or {}) if isinstance(meta.get("author"), dict) else {}
    # `gh pr view --json author` reports `is_bot`, while the REST API reports
    # `type`. Without this translation the classifier sees neither and calls
    # every PR human.
    if "type" not in author and author.get("is_bot") is not None:
        author["type"] = "Bot" if author["is_bot"] else "User"
    commits = []
    for entry in _pages(commits_payload):
        if not isinstance(entry, dict):
            continue
        commit_author = (entry.get("commit") or {}).get("author") or {}
        commits.append(f"{commit_author.get('name') or ''} <{commit_author.get('email') or ''}>")

    files = []
    for entry in _pages(files_payload):
        if not isinstance(entry, dict):
            continue
        files.append(
            {
                "filename": entry.get("filename") or "",
                "additions": entry.get("additions") or 0,
                "deletions": entry.get("deletions") or 0,
            }
        )

    return {
        "author": author,
        "branch": meta.get("headRefName") or "",
        "body": meta.get("body") or "",
        "commits": commits,
        "files": files,
    }


def compute_labels(facts: dict) -> set[str]:
    """Return every label the managed axes imply for one pull request.

    ``facts`` may be missing any key; a missing key is an absent signal, never
    an error, because a half-populated payload should still label the PR.
    """
    author = facts.get("author") or {}
    files = facts.get("files") or []
    filenames = [entry.get("filename", "") for entry in files if isinstance(entry, dict)]

    labels = {
        classify(
            author.get("login", ""),
            author.get("type", ""),
            facts.get("branch", ""),
            facts.get("commits") or [],
        )
    }
    labels.add(
        size_label(
            sum(entry.get("additions", 0) for entry in files if isinstance(entry, dict)),
            sum(entry.get("deletions", 0) for entry in files if isinstance(entry, dict)),
        )
    )
    labels |= domain_labels(filenames)
    if is_dependency_change(filenames):
        labels.add(DEPENDENCY_LABEL)
    labels |= telemetry_labels(facts.get("body"))
    return labels


def main(argv: list[str] | None = None) -> int:
    """Print labels for the workflow: computed from stdin, or ``--managed``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--managed",
        action="store_true",
        help="print every label this system may add or remove, then exit",
    )
    parser.add_argument(
        "--facts",
        metavar="PATH",
        help=(
            "read a JSON object with meta, commits, and files keys (as returned "
            "by `gh api --paginate --slurp`), build the fact sheet, and print labels"
        ),
    )
    args = parser.parse_args(argv)

    if args.managed:
        for label in sorted(MANAGED_LABELS):
            print(label)
        return 0

    try:
        if args.facts:
            with open(args.facts, encoding="utf-8") as handle:
                payload = json.load(handle)
            facts = build_facts(
                payload.get("meta"),
                payload.get("commits"),
                payload.get("files"),
            )
        else:
            facts = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, AttributeError) as error:
        print(f"could not read pull request facts: {error}", file=sys.stderr)
        return 1

    for label in sorted(compute_labels(facts)):
        print(label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
