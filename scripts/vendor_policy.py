"""Licence policy for the vendor alley (issue #383).

`apps/studio/src/vendor/ledger.test.ts` proves a copied file's header agrees with
its entry in `apps/studio/vendor.lock.json`. Two rules cannot be checked from
inside that tree, so they live here, in the suite the licence CI job runs:

- **a licence id we can parse is not one we can ship.** `MIT` and `GPL-3.0` have
  the same shape. The allowlist is the set of ids whose terms we have read and
  accept, so it is asserted against a closed list rather than a pattern.
- **rule 1 of `docs/architecture/vendor.md` makes behaviour primitives
  dependencies, not copies** — which means the npm packages a copy imports are
  part of the audit even though nobody copied their source. They are ledgered in
  that document and cross-checked against what the tree actually imports and
  what `apps/studio/package.json` actually declares.

The checks are pure functions over text so the tests can inject synthetic
input, exactly like `scripts/pr_guards.py`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from doc_check import _section_lines

ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = ROOT / "apps/studio/src/vendor"
LOCK_PATH = ROOT / "apps/studio/vendor.lock.json"
PACKAGE_JSON_PATH = ROOT / "apps/studio/package.json"
POLICY_PATH = ROOT / "docs/architecture/vendor.md"

#: The SPDX ids whose terms this repository accepts for copied code.
SPDX_ALLOWLIST = frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "ISC", "0BSD"})

DEPENDENCY_HEADING = "## The dependencies the alley needs"
DEPENDENCY_COLUMNS = ("Package", "Licence", "Declared in", "Why the alley needs it")

#: A copy-in arrives as source, a stylesheet or a policy note; never as a test.
LEDGERED_SUFFIXES = (".ts", ".tsx", ".css", ".md")
#: Prose documents an import, it does not perform one.
IMPORTING_SUFFIXES = (".ts", ".tsx", ".css")

_TEST_FILE = re.compile(r"\.test\.tsx?$")
#: `from "x"`, `import x from "y"`, `import "z"` and CSS `@import "w"`, but not
#: a sentence that happens to contain the word import.
_SPECIFIER = re.compile(r"""(?:^|[^.\w])(?:from|import)\s*\(?\s*["']([^"']+)["']""")
_SEPARATOR = re.compile(r":?-{2,}:?")


def package_name(specifier: str) -> str | None:
    """The npm package whose licence covers this specifier, or None.

    Aliased (`@/state/*`) and relative specifiers resolve inside the tree, and a
    `node:` builtin ships with the runtime: none of them have an upstream to
    attribute.
    """
    if specifier.startswith((".", "@/", "node:")):
        return None
    parts = specifier.split("/")
    if parts[0].startswith("@"):
        return f"{parts[0]}/{parts[1]}" if len(parts) > 1 else None
    return parts[0] or None


def imported_packages(sources: dict[str, str]) -> set[str]:
    """Every package the alley's shipped sources and stylesheets pull in."""
    names: set[str] = set()
    for path, text in sources.items():
        if not path.endswith(IMPORTING_SUFFIXES):
            continue
        for specifier in _SPECIFIER.findall(text):
            name = package_name(specifier)
            if name is not None:
                names.add(name)
    return names


def vendored_sources(vendor_dir: Path = VENDOR_DIR) -> dict[str, str]:
    """Ledger-relative path to source text for every file the ledger must name.

    A file is tracked whatever the lock claims about its origin: only the
    absence of an entry is an offence here, and a test of the alley is not a
    copy, so `*.test.ts(x)` stays out of both lists.
    """
    sources: dict[str, str] = {}
    for path in sorted(vendor_dir.rglob("*")):
        if not path.is_file() or not path.name.endswith(LEDGERED_SUFFIXES):
            continue
        if _TEST_FILE.search(path.name):
            continue
        sources[str(path.relative_to(vendor_dir))] = path.read_text(encoding="utf-8")
    return sources


def dependency_ledger(doc: str) -> list[dict[str, str]]:
    """Rows of the dependency table under `DEPENDENCY_HEADING`, or an empty list.

    The header row is the contract. A table with other columns is not this
    ledger, and reading it as one is how a policy stops being checked while
    looking checked.
    """
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in _section_lines(doc, DEPENDENCY_HEADING)
        if line.strip().startswith("|")
    ]
    if not rows or tuple(rows[0]) != DEPENDENCY_COLUMNS:
        return []
    data = [row for row in rows[1:] if not all(_SEPARATOR.fullmatch(cell) for cell in row)]
    if any(len(row) != len(DEPENDENCY_COLUMNS) for row in data):
        return []
    ledger = [dict(zip(DEPENDENCY_COLUMNS, row, strict=True)) for row in data]
    for row in ledger:
        row["Package"] = row["Package"].strip("`")
    return ledger


def _entries(lock: dict[str, Any], section: str) -> dict[str, Any]:
    entries = lock.get(section, {})
    return entries if isinstance(entries, dict) else {}


def _declared_sections(package_json_text: str) -> dict[str, str]:
    """Package to the section that declares it; dependencies wins if both do."""
    package_json = json.loads(package_json_text)
    declared: dict[str, str] = {}
    for section in ("devDependencies", "dependencies"):
        declared.update(dict.fromkeys(package_json.get(section, {}), section))
    return declared


def policy_errors(
    lock_text: str, sources: dict[str, str], doc: str, package_json_text: str
) -> list[str]:
    """Every way the alley's records disagree with the alley, as messages.

    Empty means the copy is auditable: each file is ledgered once, each licence
    is one we ship, and each package the copies depend on is named, declared and
    attributed.
    """
    lock = json.loads(lock_text)
    vendored = _entries(lock, "vendored")
    ours = _entries(lock, "firstParty")
    declared = _declared_sections(package_json_text)
    errors: list[str] = []

    for section, entries in (("vendored", vendored), ("firstParty", ours)):
        if list(entries) != sorted(entries):
            errors.append(
                f"the {section} entries in {LOCK_PATH.relative_to(ROOT)} are not sorted by path"
            )

    for path in sorted(set(sources) - set(vendored) - set(ours)):
        errors.append(f"{path} is in the vendor alley but has no vendor.lock.json entry")
    for path in sorted((set(vendored) | set(ours)) - set(sources)):
        errors.append(f"{path} is in vendor.lock.json but no such file is in the alley")
    for path in sorted(set(vendored) & set(ours)):
        errors.append(f"{path} is listed in vendor.lock.json as both vendored and first-party")

    for path, entry in sorted(vendored.items()):
        licence = str(entry.get("licence", ""))
        if licence not in SPDX_ALLOWLIST:
            errors.append(f"{path} is copied under {licence!r}, which is not on the SPDX allowlist")

    rows = dependency_ledger(doc)
    if not rows:
        errors.append(
            f"{DEPENDENCY_HEADING} is missing from docs/architecture/vendor.md, so the "
            f"packages the copies depend on are not ledgered"
        )
        return errors

    ledger = {row["Package"]: row for row in rows}
    imported = imported_packages(sources)

    for package, row in sorted(ledger.items()):
        if row["Licence"] not in SPDX_ALLOWLIST:
            errors.append(
                f"{package} is depended on under {row['Licence']!r}, "
                f"which is not on the SPDX allowlist"
            )
    for package in sorted(imported - set(ledger)):
        errors.append(f"{package} is imported by the alley but is not in its dependency ledger")
    for package in sorted(set(ledger) - imported):
        errors.append(f"{package} is in the dependency ledger but no file in the alley imports it")
    for package in sorted(imported & set(ledger)):
        section = ledger[package]["Declared in"]
        if package not in declared:
            errors.append(
                f"{package} is imported by the alley but declared nowhere in "
                f"{PACKAGE_JSON_PATH.relative_to(ROOT)}"
            )
        elif declared[package] != section:
            errors.append(
                f"{package} is ledgered as a {section} of "
                f"{PACKAGE_JSON_PATH.relative_to(ROOT)} but is declared in {declared[package]}"
            )
    return errors


def check() -> list[str]:
    """`policy_errors` over the files this repository actually ships."""
    return policy_errors(
        LOCK_PATH.read_text(encoding="utf-8"),
        vendored_sources(),
        POLICY_PATH.read_text(encoding="utf-8"),
        PACKAGE_JSON_PATH.read_text(encoding="utf-8"),
    )
