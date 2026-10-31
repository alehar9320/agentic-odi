"""Tests for the vendored-file policy (issue #383)."""

from __future__ import annotations

import json
from pathlib import Path

from vendor_policy import (
    ALLOWED_SPDX,
    HEADER_MARKER,
    check_ledger,
    check_packages,
    parse_vendored_header,
    repository_violations,
    vendor_sources,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDIO_ROOT = REPO_ROOT / "apps" / "studio"
VENDOR_ROOT = STUDIO_ROOT / "src" / "vendor"

UPSTREAM = "https://ui.shadcn.com"
COMMIT = "shadcn-cli-4.23.0"
HEADER = f"{HEADER_MARKER} {UPSTREAM}@{COMMIT} — MIT — local edits: none\n"


def _entry(path: str = "components/ui/card.tsx", **overrides: object) -> dict[str, object]:
    entry = {
        "path": path,
        "upstream": UPSTREAM,
        "commit": COMMIT,
        "copied_at": "2026-10-31",
        "spdx": "MIT",
        "local_edits": "none",
    }
    entry.update(overrides)
    return entry


def _ledger(*entries: dict[str, object]) -> list[dict[str, object]]:
    return list(entries)


# --- the header line ---------------------------------------------------------


def test_a_vendored_header_is_read_into_its_parts() -> None:
    parsed = parse_vendored_header(HEADER + "export const x = 1\n")

    assert parsed is not None
    assert parsed["upstream"] == UPSTREAM
    assert parsed["commit"] == COMMIT
    assert parsed["spdx"] == "MIT"
    assert parsed["local_edits"] == "none"


def test_a_file_without_the_header_is_not_vendored() -> None:
    assert parse_vendored_header("export const x = 1\n") is None


# --- ledger and tree must agree ---------------------------------------------


def test_an_unlisted_copied_file_is_reported_by_name() -> None:
    sources = {"components/ui/card.tsx": HEADER, "components/ui/badge.tsx": HEADER}

    errors = check_ledger(_ledger(_entry()), sources)

    assert len(errors) == 1
    assert "components/ui/badge.tsx" in errors[0]


def test_removing_a_ledger_entry_names_the_file_it_covered() -> None:
    sources = {
        "components/ui/badge.tsx": HEADER,
        "components/ui/card.tsx": HEADER,
    }
    full = _ledger(_entry(path="components/ui/badge.tsx"), _entry(path="components/ui/card.tsx"))

    assert check_ledger(full, sources) == []
    dropped = [entry for entry in full if entry["path"] != "components/ui/card.tsx"]
    errors = check_ledger(dropped, sources)

    assert len(errors) == 1
    assert "components/ui/card.tsx" in errors[0]


def test_an_entry_for_a_file_that_is_not_in_the_tree_is_reported() -> None:
    errors = check_ledger(_ledger(_entry()), {})

    assert len(errors) == 1
    assert "components/ui/card.tsx" in errors[0]


def test_two_entries_for_one_path_are_reported() -> None:
    sources = {"components/ui/card.tsx": HEADER}

    errors = check_ledger(_ledger(_entry(), _entry()), sources)

    assert any("duplicate" in error.lower() for error in errors)


def test_entries_have_to_be_sorted_for_stable_diffs() -> None:
    sources = {
        "components/ui/a.tsx": HEADER,
        "components/ui/b.tsx": HEADER,
    }
    unsorted = _ledger(_entry(path="components/ui/b.tsx"), _entry(path="components/ui/a.tsx"))

    errors = check_ledger(unsorted, sources)

    assert len(errors) == 1
    assert "sorted" in errors[0].lower()


# --- licence and revision truthfulness ---------------------------------------


def test_only_the_allowed_licences_are_accepted() -> None:
    assert ALLOWED_SPDX == frozenset({"MIT", "Apache-2.0", "BSD-2-Clause", "ISC", "0BSD"})

    errors = check_ledger(_ledger(_entry(spdx="GPL-3.0-only")), {"components/ui/card.tsx": HEADER})

    assert any("GPL-3.0-only" in error and "not allowed" in error for error in errors)


def test_a_header_naming_another_revision_than_the_ledger_is_stale() -> None:
    stale = f"{HEADER_MARKER} {UPSTREAM}@shadcn-cli-3.0.0 — MIT — local edits: none\n"
    sources = {"components/ui/card.tsx": stale}

    errors = check_ledger(_ledger(_entry()), sources)

    assert len(errors) == 1
    assert "shadcn-cli-3.0.0" in errors[0]
    assert "stale" in errors[0].lower()


def test_a_header_without_a_recorded_revision_is_reported() -> None:
    sources = {"components/ui/card.tsx": "export const x = 1\n"}

    errors = check_ledger(_ledger(_entry()), sources)

    assert len(errors) == 1
    assert "header" in errors[0].lower()


def test_an_undated_or_placeholder_copy_is_reported() -> None:
    sources = {"components/ui/card.tsx": HEADER}

    assert check_ledger(_ledger(_entry(copied_at="not-a-date")), sources)
    assert check_ledger(_ledger(_entry(commit="unknown")), sources)


def test_local_edits_have_to_say_something() -> None:
    sources = {"components/ui/card.tsx": HEADER}

    assert check_ledger(_ledger(_entry(local_edits="")), sources)


# --- the dependencies vendoring pulled in -------------------------------------


def test_a_package_that_is_not_a_dependency_of_the_studio_is_reported() -> None:
    errors = check_packages(
        [{"name": "radix-ui", "spdx": "MIT", "why": "the copied button imports Slot from it"}],
        declared={"clsx"},
    )

    assert len(errors) == 1
    assert "radix-ui" in errors[0]


def test_a_package_entry_needs_a_licence_and_a_reason() -> None:
    errors = check_packages(
        [{"name": "clsx", "spdx": "", "why": ""}],
        declared={"clsx"},
    )

    assert len(errors) == 2


# --- the repository as it actually stands -------------------------------------


def test_the_shipped_ledger_matches_the_shipped_vendor_tree() -> None:
    assert repository_violations(STUDIO_ROOT) == []


def test_the_ledger_file_is_valid_json_sorted_by_path() -> None:
    raw = json.loads((STUDIO_ROOT / "vendor.lock.json").read_text(encoding="utf-8"))

    paths = [entry["path"] for entry in raw["files"]]
    assert paths == sorted(paths)
    assert paths, "the ledger has to cover the copied tree"
    assert set(raw) == {"files", "packages"}


def test_only_copied_surfaces_are_audited_and_tests_are_not() -> None:
    sources = vendor_sources(VENDOR_ROOT)

    assert "components/ui/button.tsx" in sources
    assert not [path for path in sources if path.endswith(".test.tsx")]
