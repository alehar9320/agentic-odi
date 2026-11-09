"""Tests for the assistant-ui ledger check in scripts/doc_check.py (issue #429).

The ledger is only honest if a machine holds it honest: an Adopted row must
name a file that exists and cite a delivery the repository's history proves;
a Planned row must not cite one that already merged; the counts and the Living
Studio projection must match the rows. These tests run on synthetic tables
with an injected delivered set — never git — so they pass on a shallow CI
checkout, exactly like the docs job's full-history run but offline.
"""

from __future__ import annotations

from pathlib import Path

from doc_check import ROOT, delivered_references, ledger_errors

LEDGER_HEAD = """## The assistant-ui ledger

Prose.

### Runtime

| Capability | Status | File | Delivered | Where / why |
|---|---|---|---|---|
"""

PROJECTION_HEAD = """#### What the runtime gives us, and what we did not take

| Capability | Status | What it means here | Delivered |
|---|---|---|---|
"""

COUNTS = """
### The count

| Status | Rows |
|---|---|
| Adopted | 1 |
| Partial | 0 |
| Planned | 1 |
| Decision | 0 |
| Rejected | 0 |
| Total | 2 |
"""

_ADOPTED = "| `useThing` | Adopted | `pkg/src/thing.ts` | #7 | It works. |\n"
_PLANNED = "| `queueThing` | Planned | — | #9 | Later. |\n"
_PROJECTION = "| `useThing` | Adopted | It works. | #7 |\n"


def _ledger(rows: str, counts: str = COUNTS) -> str:
    return LEDGER_HEAD + rows + counts


def _projection(rows: str) -> str:
    return PROJECTION_HEAD + rows


def _tree(root: Path) -> Path:
    target = root / "pkg/src"
    target.mkdir(parents=True)
    (target / "thing.ts").write_text("export {}\n", encoding="utf-8")
    return root


def test_a_clean_ledger_passes(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    issues = ledger_errors(
        _ledger(_ADOPTED + _PLANNED),
        _projection(_PROJECTION),
        root=root,
        delivered={"7"},
    )
    assert issues == []


def test_an_adopted_row_without_a_citation_is_in_progress_not_adopted(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    uncited = _ADOPTED.replace("| #7 |", "| — |")
    issues = ledger_errors(
        _ledger(uncited + _PLANNED), _projection(_PROJECTION), root=root, delivered={"7"}
    )
    assert any("without a merged citation" in issue for issue in issues)


def test_an_adopted_row_citing_an_unmerged_number_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    issues = ledger_errors(
        _ledger(_ADOPTED + _PLANNED),
        _projection(_PROJECTION),
        root=root,
        delivered={"8"},
    )
    assert any("history does not prove merged" in issue for issue in issues)


def test_a_planned_row_citing_an_already_merged_issue_is_stale(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    issues = ledger_errors(
        _ledger(_ADOPTED + _PLANNED), _projection(_PROJECTION), root=root, delivered={"7", "9"}
    )
    assert any("which already merged" in issue for issue in issues)


def test_an_adopted_row_naming_a_missing_file_fails(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    issues = ledger_errors(
        _ledger(_ADOPTED + _PLANNED), _projection(_PROJECTION), root=root, delivered={"7"}
    )
    assert any("does not exist" in issue for issue in issues)


def test_projection_drift_is_caught(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    issues = ledger_errors(
        _ledger(_ADOPTED + _PLANNED),
        _projection(""),
        root=root,
        delivered={"7"},
    )
    assert any("projection is missing a ledger row" in issue for issue in issues)
    issues = ledger_errors(
        _ledger(_ADOPTED + _PLANNED),
        _projection(_PROJECTION + "| `ghostThing` | Adopted | Nope. | #7 |\n"),
        root=root,
        delivered={"7"},
    )
    assert any("does not adopt" in issue for issue in issues)


def test_count_table_must_match_the_rows(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    wrong = COUNTS.replace("| Adopted | 1 |", "| Adopted | 2 |")
    issues = ledger_errors(
        _ledger(_ADOPTED + _PLANNED, counts=wrong),
        _projection(_PROJECTION),
        root=root,
        delivered={"7"},
    )
    assert any("count table says 2 Adopted" in issue for issue in issues)


def test_unknown_status_is_rejected(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    bogus = _ADOPTED.replace("Adopted", "Shipped")
    issues = ledger_errors(
        _ledger(bogus + _PLANNED), _projection(_PROJECTION), root=root, delivered={"7"}
    )
    assert any("unknown ledger status" in issue for issue in issues)


def test_duplicate_capability_rows_are_caught(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    issues = ledger_errors(
        _ledger(_ADOPTED + _ADOPTED), _projection(_PROJECTION), root=root, delivered={"7"}
    )
    assert any("duplicate ledger row" in issue for issue in issues)


def test_no_ledger_anywhere_is_silent(tmp_path: Path) -> None:
    assert ledger_errors("", "", root=tmp_path) == []


def test_projection_without_its_source_is_caught(tmp_path: Path) -> None:
    issues = ledger_errors("", PROJECTION_HEAD, root=tmp_path)
    assert issues == ["ledger projection exists but the source section is missing"]


def test_delivered_references_ignores_merge_commits() -> None:
    subjects = [
        "feat(studio): quote a passage into the composer (#435)",
        "Merge remote-tracking branch 'origin/main' into topic (#77)",
        "feat(studio): recall sent messages with the up arrow (#427) (#430)",
    ]
    assert delivered_references(subjects) == {"435", "427", "430"}


def test_the_repository_ledger_is_honest() -> None:
    """The real table passes every structural rule with history-independent checks."""
    source = (ROOT / "docs/development.md").read_text(encoding="utf-8")
    projection = (ROOT / "docs/living-studio.md").read_text(encoding="utf-8")
    assert ledger_errors(source, projection, root=ROOT, delivered=None) == []
