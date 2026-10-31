#!/usr/bin/env python3
"""Audit the vendored files under `apps/studio/src/vendor` (issue #383).

A copied component is a dependency nobody chose deliberately: it arrives with a
licence, an upstream revision, and whatever local edits the copier made. This
module keeps that record true by comparing the ledger at
`apps/studio/vendor.lock.json` against the tree it claims to describe, and both
against the header line each copied file carries.

Paths in the ledger are relative to `apps/studio/src/vendor`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path

ALLOWED_SPDX = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "ISC", "0BSD"})
HEADER_MARKER = "// vendored:"
PLACEHOLDER_REVISIONS = frozenset(
    {"", "unknown", "latest", "head", "main", "master", "none", "n/a"}
)

# `// vendored: <upstream url>@<commit> — <SPDX> — local edits: <none|what>`
_HEADER_RE = re.compile(
    r"^// vendored:\s+"
    r"(?P<upstream>\S+)@(?P<commit>\S+)\s+—\s+"
    r"(?P<spdx>\S+)\s+—\s+"
    r"local edits:\s+(?P<local_edits>.+?)\s*$",
    re.MULTILINE,
)

COPIED_SURFACE = "components/"


def parse_vendored_header(text: str) -> dict[str, str] | None:
    """Return the parts of a `// vendored:` header, or None when there is none."""
    match = _HEADER_RE.search(text[:4000])
    if match is None:
        return None
    return match.groupdict()


def vendor_sources(vendor_root: Path) -> dict[str, str]:
    """Map every audited file under the vendor root to its text.

    Audited means: a TypeScript source under the copied surface, or any source
    that carries a vendored header. Tests and hand-written helpers are not
    copies, so a ledger entry for one would be a provenance record nobody can
    check.
    """
    sources: dict[str, str] = {}
    for path in sorted(vendor_root.rglob("*")):
        if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
            continue
        relative = path.relative_to(vendor_root).as_posix()
        if ".test." in relative:
            continue
        text = path.read_text(encoding="utf-8")
        if relative.startswith(COPIED_SURFACE) or parse_vendored_header(text):
            sources[relative] = text
    return sources


def _entry_paths(entries: Sequence[Mapping[str, object]]) -> list[str]:
    return [str(entry.get("path", "")) for entry in entries]


def check_ledger(
    entries: Sequence[Mapping[str, object]],
    sources: Mapping[str, str],
) -> list[str]:
    """Report every way the ledger and the tree disagree."""
    errors: list[str] = []
    paths = _entry_paths(entries)

    if len(set(paths)) != len(paths):
        repeated = sorted({path for path in paths if paths.count(path) > 1})
        errors.append(f"Duplicate ledger entries for {', '.join(repeated)}.")
    if paths != sorted(paths):
        errors.append("Ledger entries must be sorted by path so diffs stay stable.")

    by_path: dict[str, Mapping[str, object]] = {}
    for entry in entries:
        by_path[str(entry.get("path", ""))] = entry

    for path in sorted(sources):
        if path not in by_path:
            errors.append(f"{path} is copied but has no entry in vendor.lock.json.")
    for path in sorted(by_path):
        if path not in sources:
            errors.append(f"vendor.lock.json lists {path}, which is not in the vendor tree.")

    for path, entry in sorted(by_path.items()):
        text = sources.get(path)
        if text is None:
            continue
        errors.extend(_check_entry(path, entry, text))
    return errors


def _check_entry(path: str, entry: Mapping[str, object], text: str) -> list[str]:
    errors: list[str] = []
    spdx = str(entry.get("spdx", ""))
    commit = str(entry.get("commit", ""))
    copied_at = str(entry.get("copied_at", ""))
    local_edits = str(entry.get("local_edits", ""))

    if spdx not in ALLOWED_SPDX:
        errors.append(f"{path} records licence {spdx or 'nothing'}, which is not allowed.")
    if commit.strip().lower() in PLACEHOLDER_REVISIONS:
        errors.append(f"{path} records no upstream revision.")
    if local_edits.strip() == "":
        errors.append(f"{path} leaves local edits blank; write 'none' or say what changed.")
    try:
        date.fromisoformat(copied_at)
    except ValueError:
        errors.append(f"{path} records copied_at {copied_at!r}, which is not an ISO date.")

    header = parse_vendored_header(text)
    if header is None:
        errors.append(
            f"{path} has no `{HEADER_MARKER} <upstream>@<commit> — <SPDX> — local edits: …` header."
        )
        return errors
    if header["commit"] != commit:
        errors.append(
            f"{path} is stale: its header says {header['commit']}, vendor.lock.json says {commit}."
        )
    if header["spdx"] != spdx:
        errors.append(
            f"{path} is stale: its header says {header['spdx']}, vendor.lock.json says {spdx}."
        )
    if header["upstream"] != str(entry.get("upstream", "")):
        errors.append(
            f"{path} is stale: its header points at {header['upstream']},"
            f" vendor.lock.json says {entry.get('upstream', '')}."
        )
    return errors


def check_packages(
    packages: Iterable[Mapping[str, object]],
    declared: Iterable[str],
) -> list[str]:
    """Report ledger packages the Studio does not actually depend on."""
    known = set(declared)
    errors: list[str] = []
    for package in packages:
        name = str(package.get("name", ""))
        if name not in known:
            errors.append(f"{name} is in the ledger but not a dependency of apps/studio.")
        spdx = str(package.get("spdx", ""))
        if spdx == "":
            errors.append(f"{name} records no licence.")
        elif spdx not in ALLOWED_SPDX:
            errors.append(f"{name} records licence {spdx}, which is not allowed.")
        if str(package.get("why", "")).strip() == "":
            errors.append(f"{name} gives no reason for being here.")
    return errors


def repository_violations(studio_root: Path) -> list[str]:
    """Check the shipped ledger against the shipped tree."""
    lock_path = studio_root / "vendor.lock.json"
    if not lock_path.is_file():
        return [f"{lock_path} does not exist."]
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    package_json = json.loads((studio_root / "package.json").read_text(encoding="utf-8"))
    declared = set(package_json.get("dependencies", {})) | set(
        package_json.get("devDependencies", {})
    )
    errors = check_ledger(
        lock.get("files", []),
        vendor_sources(studio_root / "src" / "vendor"),
    )
    errors.extend(check_packages(lock.get("packages", []), declared))
    return errors


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--studio-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "apps" / "studio",
    )
    args = parser.parse_args()
    violations = repository_violations(args.studio_root)
    for violation in violations:
        print(violation)
    if violations:
        print(f"vendor policy: {len(violations)} violation(s)")
        return 1
    print("vendor policy: ledger and tree agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
