"""Compute the labels a reviewer should see on a pull request.

Every function here is pure: give it facts about a pull request, get labels
back. The workflow gathers the facts with ``gh``; this module never touches the
network, so its behaviour can be pinned by tests.
"""

from __future__ import annotations

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
        # Longest directory match wins, so a future apps/studio-api rule cannot
        # be shadowed by the shorter apps/studio rule.
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
