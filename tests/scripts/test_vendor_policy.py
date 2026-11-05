"""Tests for scripts/vendor_policy.py (issue #383).

`apps/studio/src/vendor/ledger.test.ts` already holds a copied file's header to
its entry in `apps/studio/vendor.lock.json`. Two parts of the policy live
outside what a test inside that tree can see:

- a licence id that is well-formed is not one we may necessarily ship, so the
  allowlist is checked here as well, in the language of the CI job that guards
  licences;
- rule 1 of `docs/architecture/vendor.md` makes behaviour primitives
  dependencies rather than copies, so the packages the copies import belong to
  the audit even though nobody copied their source.

Like `test_pr_guards.py`, the unit tests run on synthetic input with every path
injected; only the last test reads the repository.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vendor_policy import (
    DEPENDENCY_COLUMNS,
    DEPENDENCY_HEADING,
    SPDX_ALLOWLIST,
    check,
    dependency_ledger,
    imported_packages,
    package_name,
    policy_errors,
    vendored_sources,
)

_BUTTON = "components/ui/button.tsx"
_README = "components/ui/README.md"

_LOCK = json.dumps(
    {
        "vendored": {
            _BUTTON: {
                "source": "https://ui.shadcn.com/r/styles/new-york-v4/button.json",
                "licence": "MIT",
            }
        },
        "firstParty": {
            _README: "Policy summary for this directory.",
            "lib/utils.ts": "Three-line class merger, written here.",
        },
    }
)

_SOURCES = {
    _BUTTON: (
        'import * as React from "react"\n'
        'import { cva } from "class-variance-authority"\n'
        'import { cn } from "@/lib/utils"\n'
        'import { Slot } from "radix-ui"\n'
    ),
    # A README documents a copy; it does not become one. The lodash line is
    # here so the baseline proves it costs no ledger row.
    _README: 'Copy it with `import { Button } from "lodash"`.\n',
    "lib/utils.ts": (
        'import { clsx } from "clsx";\n'
        'import { twMerge } from "tailwind-merge";\n'
        "export function cn() {}\n"
    ),
}

_ROWS = (
    ("react", "MIT", "dependencies"),
    ("class-variance-authority", "MIT", "devDependencies"),
    ("radix-ui", "MIT", "dependencies"),
    ("clsx", "MIT", "devDependencies"),
    ("tailwind-merge", "MIT", "devDependencies"),
)

_PACKAGES = json.dumps(
    {
        "dependencies": {"react": "^19.3.1", "radix-ui": "^1.8.1"},
        "devDependencies": {
            "class-variance-authority": "^0.7.1",
            "clsx": "^2.1.1",
            "tailwind-merge": "^3.7.0",
        },
    }
)


def _doc(rows: tuple[tuple[str, str, str], ...] = _ROWS) -> str:
    lines = [
        DEPENDENCY_HEADING,
        "",
        f"| {' | '.join(DEPENDENCY_COLUMNS)} |",
        "|" + " --- |" * len(DEPENDENCY_COLUMNS),
    ]
    for name, licence, section in rows:
        lines.append(f"| `{name}` | {licence} | {section} | Because the copies say so. |")
    return "\n".join(lines) + "\n"


def _lock(**overrides: dict[str, Any]) -> str:
    lock = json.loads(_LOCK)
    for section, entries in overrides.items():
        lock[section] = entries
    return json.dumps(lock)


def _errors(**overrides: Any) -> list[str]:
    inputs: dict[str, Any] = {
        "lock": _LOCK,
        "sources": _SOURCES,
        "doc": _doc(),
        "packages": _PACKAGES,
    }
    inputs.update(overrides)
    return policy_errors(
        inputs["lock"],
        inputs["sources"],
        inputs["doc"],
        inputs["packages"],
    )


def _named(errors: list[str], *needles: str) -> bool:
    return any(all(needle in error for needle in needles) for error in errors)


# --- the allowlist ------------------------------------------------------------


def test_the_allowlist_is_exactly_the_five_ids_the_policy_names() -> None:
    assert SPDX_ALLOWLIST == frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "ISC", "0BSD"})


def test_a_copied_file_under_an_unshippable_licence_names_the_file() -> None:
    errors = _errors(lock=_lock(vendored={_BUTTON: {"licence": "GPL-3.0"}}))

    assert _named(errors, "GPL-3.0", _BUTTON), errors


def test_a_dependency_under_an_unshippable_licence_names_the_package() -> None:
    rows = (("react", "GPL-3.0", "dependencies"),) + _ROWS[1:]
    errors = _errors(doc=_doc(rows))

    assert _named(errors, "GPL-3.0", "react"), errors


# --- the ledger against the tree ---------------------------------------------


def test_the_baseline_ledger_is_clean() -> None:
    assert _errors() == []


def test_a_file_that_arrived_without_a_ledger_entry_is_named() -> None:
    sources = {**_SOURCES, "components/ui/card.tsx": 'import { cn } from "@/lib/utils";\n'}
    errors = _errors(sources=sources)

    assert _named(errors, "components/ui/card.tsx"), errors


def test_a_lock_entry_for_a_file_that_is_gone_is_named() -> None:
    errors = _errors(
        lock=_lock(
            vendored={_BUTTON: {"licence": "MIT"}, "components/ui/ghost.tsx": {"licence": "MIT"}}
        )
    )

    assert _named(errors, "components/ui/ghost.tsx"), errors


def test_one_path_cannot_be_listed_as_both_copied_and_ours() -> None:
    errors = _errors(lock=_lock(firstParty={_README: "ours", _BUTTON: "also ours?"}))

    assert _named(errors, _BUTTON), errors


def test_the_lock_is_ordered_by_path_so_a_refresh_diff_stays_small() -> None:
    errors = _errors(lock=_lock(firstParty={"lib/utils.ts": "ours", _README: "ours"}))

    assert _named(errors, "firstParty", "sorted"), errors


# --- the dependency ledger ----------------------------------------------------


def test_every_package_a_copy_imports_needs_a_ledger_row() -> None:
    rows = tuple(row for row in _ROWS if row[0] != "clsx")
    errors = _errors(doc=_doc(rows))

    assert _named(errors, "clsx"), errors


def test_a_ledger_row_that_no_copy_imports_is_stale() -> None:
    errors = _errors(doc=_doc(_ROWS + (("@tanstack/react-virtual", "MIT", "dependencies"),)))

    assert _named(errors, "@tanstack/react-virtual"), errors


def test_a_package_the_copies_import_must_be_declared_in_package_json() -> None:
    sources = {**_SOURCES, _BUTTON: _SOURCES[_BUTTON] + 'import { nanoid } from "nanoid";\n'}
    rows = _ROWS + (("nanoid", "MIT", "devDependencies"),)
    errors = _errors(sources=sources, doc=_doc(rows))

    assert _named(errors, "nanoid", "apps/studio/package.json"), errors


def test_the_ledger_records_the_section_that_actually_declares_the_package() -> None:
    rows = tuple(
        ("clsx", "MIT", "dependencies") if name == "clsx" else (name, licence, section)
        for name, licence, section in _ROWS
    )
    errors = _errors(doc=_doc(rows))

    assert _named(errors, "clsx", "dependencies", "devDependencies"), errors


def test_a_missing_dependency_table_is_reported_once_not_per_package() -> None:
    errors = _errors(doc="## How the rules are enforced\n\nNothing here.\n")

    assert len(errors) == 1, errors
    assert DEPENDENCY_HEADING in errors[0], errors


def test_a_table_under_the_heading_with_the_wrong_columns_is_not_a_ledger() -> None:
    doc = f"{DEPENDENCY_HEADING}\n\n| Package | Version |\n| --- | --- |\n| `react` | ^19.3.1 |\n"
    errors = _errors(doc=doc)

    assert _named(errors, DEPENDENCY_HEADING), errors


# --- reading a specifier ------------------------------------------------------


def test_a_specifier_resolves_to_the_package_that_ships_its_licence() -> None:
    assert package_name("@radix-ui/react-slot") == "@radix-ui/react-slot"
    assert package_name("tailwindcss/utilities.css") == "tailwindcss"
    assert package_name("clsx") == "clsx"
    assert package_name("@/lib/utils") is None
    assert package_name("../state/StudioContext") is None
    assert package_name("node:fs") is None


def test_a_vendored_stylesheet_imports_packages_too() -> None:
    sources = {"index.css": '@import "tailwindcss/utilities.css" layer(utilities) source(none);\n'}

    assert imported_packages(sources) == {"tailwindcss"}


def test_a_documented_import_in_a_readme_is_not_a_dependency() -> None:
    assert (
        imported_packages({_README: 'Copy it with `import { Button } from "lodash"`.\n'}) == set()
    )


# --- walking the tree ---------------------------------------------------------


def test_the_walker_tracks_shipped_sources_and_skips_the_suite(tmp_path: Path) -> None:
    for path, text in {
        "boundary.ts": "export const x = 1;\n",
        "index.css": "@layer theme;\n",
        "ledger.test.ts": 'import { x } from "vitest";\n',
        _README: "Policy summary.\n",
        _BUTTON: "export const Button = 1;\n",
        "package.example.json": "{}\n",
    }.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    assert set(vendored_sources(tmp_path)) == {
        "boundary.ts",
        "index.css",
        _README,
        _BUTTON,
    }


def test_the_parser_reads_the_shipped_ledger_as_data() -> None:
    rows = dependency_ledger(_doc())

    assert [row["Package"] for row in rows] == [name for name, _, _ in _ROWS]
    assert rows[0]["Licence"] == "MIT"


# --- the repository itself ----------------------------------------------------


def test_the_shipped_alley_and_its_ledger_agree() -> None:
    assert check() == []
