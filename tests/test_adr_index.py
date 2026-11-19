"""The ADR index is the only map of ``docs/architecture/adr/``, and it is written by hand.

``docs/architecture/adr/README.md`` states the format every record follows and
lists the records in a table. Both halves drift quietly: a record added without a
row is invisible to a reader who starts at the index, and a row whose file was
renamed is a link that 404s. ``tests/test_docs_code_overview.py`` holds the
README's Code Overview table to that standard in both directions; this does it
for the ADRs, and holds each record to the sections the index promises.

The second half of this file is about a rule that does not live in the
repository. ``main-requires-ci-green`` is a GitHub ruleset: no file in the tree
can read it, so no file in the tree can keep it honest. What the tree can do is
refuse to document a required check that no workflow produces. The ruleset
requires the ``CI green`` and ``PR guardrails`` checks by name, and a workflow
that renames its job renames what the ruleset waits for — silently, and only at
merge time. So the job names are read out of the workflows and compared with the
table in ``docs/development.md`` and the ruleset paragraph in
``docs/architecture/README.md``.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.pr_ai_authorize import REQUIRED_LABELS

ROOT = Path(__file__).resolve().parents[1]
ADR_DIR = ROOT / "docs/architecture/adr"
ADR_INDEX = ADR_DIR / "README.md"
DEVELOPMENT = ROOT / "docs/development.md"
ARCHITECTURE = ROOT / "docs/architecture/README.md"

# The jobs the `main-requires-ci-green` ruleset requires, by job id: the id is
# what the workflow file calls the job, and the name beside it is what the
# ruleset waits for. A rename of the name changes the required check without
# touching a single file the ruleset can see.
GATING_JOBS = {
    "ci-green": ROOT / ".github/workflows/ci.yml",
    "pr-guardrails": ROOT / ".github/workflows/pr-guardrails.yml",
}

SECTIONS = ("Context", "Decision", "Consequences", "Alternatives considered")
STATUS = re.compile(r"^- \*\*Status:\*\*\s*`?([^`\n]+?)`?\s*$", re.MULTILINE)
DATE = re.compile(r"^- \*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
HEADING = re.compile(r"^# (\d{4}) — (.+)$", re.MULTILINE)
INDEX_ROW = re.compile(r"^\| \[(\d{4})\]\(([^)]+)\)\s*\| ([^|]+) \| ([^|]+) \|$", re.MULTILINE)
CODE_SPAN = re.compile(r"`([^`\n]+)`")
JOB = re.compile(r"^  ([a-z0-9_-]+):\s*$")
JOB_NAME = re.compile(r"^    name: (.+?)\s*$")


def _records() -> dict[int, Path]:
    """``number -> path`` for every ADR in the directory, keyed by its number."""
    records: dict[int, Path] = {}
    for path in sorted(ADR_DIR.glob("*.md")):
        if path.name == "README.md":
            continue
        assert path.name[:4].isdigit(), f"{path.name} is not a numbered ADR"
        records[int(path.name[:4])] = path
    return records


def _rows() -> list[tuple[int, str, str, str]]:
    """``(number, link, title, status)`` for every row of the index table."""
    text = ADR_INDEX.read_text(encoding="utf-8")
    return [
        (int(number), link, title.strip(), status.strip())
        for number, link, title, status in INDEX_ROW.findall(text)
    ]


def _record_number(path: Path) -> int:
    return int(path.name[:4])


def _record_status(text: str) -> str:
    match = STATUS.search(text)
    assert match is not None, f"{text[:40]!r} has no **Status:** bullet"
    return match.group(1).strip()


def _check_names() -> set[str]:
    """The ``name:`` of every gating job, read out of its workflow."""
    names: set[str] = set()
    for job_id, workflow in GATING_JOBS.items():
        lines = workflow.read_text(encoding="utf-8").splitlines()
        inside = False
        for line in lines:
            job = JOB.match(line)
            if job is not None:
                inside = job.group(1) == job_id
                continue
            if inside:
                named = JOB_NAME.match(line)
                if named is not None:
                    names.add(named.group(1))
                    break
        assert inside, f"{workflow.relative_to(ROOT)} has no job {job_id!r}"
    return names


def _branch_protection_section() -> str:
    text = DEVELOPMENT.read_text(encoding="utf-8")
    return text.split("### Branch protection", 1)[1].split("\n## ", 1)[0]


def _table_checks(section: str) -> set[str]:
    """The status checks the guide's requirements table names, one row each."""
    checks: set[str] = set()
    for line in section.splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cell = line.split("|")[1].strip()
        if not cell or cell.startswith("Label:"):
            continue
        checks.update(CODE_SPAN.findall(cell))
    return checks


def test_every_record_has_an_index_row() -> None:
    listed = {number for number, _, _, _ in _rows()}
    missing = sorted(set(_records()) - listed)

    assert not missing, f"docs/architecture/adr/README.md has no row for: {missing}"


def test_every_index_row_resolves_to_a_record() -> None:
    records = _records()
    dangling = sorted(number for number, _, _, _ in _rows() if number not in records)

    assert not dangling, f"the index links ADRs that do not exist: {dangling}"


def test_every_index_link_names_its_own_file() -> None:
    records = _records()
    wrong = [
        f"{number} -> {link}" for number, link, _, _ in _rows() if link != records[number].name
    ]

    assert not wrong, f"the index links the wrong file: {wrong}"


def test_the_index_status_matches_the_record() -> None:
    records = _records()
    drifted = []
    for number, _, _, status in _rows():
        recorded = _record_status(records[number].read_text(encoding="utf-8"))
        if recorded != status:
            drifted.append(f"{number}: index says {status!r}, record says {recorded!r}")

    assert not drifted, f"the index disagrees with the records: {drifted}"


def test_every_record_has_the_documented_sections() -> None:
    for path in sorted(_records().values()):
        text = path.read_text(encoding="utf-8")
        missing = [name for name in SECTIONS if f"\n## {name}\n" not in text]
        assert not missing, f"{path.relative_to(ROOT)} is missing the {missing} section(s)"
        assert DATE.search(text) is not None, f"{path.relative_to(ROOT)} has no **Date:**"


def test_every_heading_matches_its_number() -> None:
    for number, path in sorted(_records().items()):
        heading = HEADING.search(path.read_text(encoding="utf-8"))
        assert heading is not None, f"{path.relative_to(ROOT)} has no '# NNNN — Title' heading"
        assert int(heading.group(1)) == number, (
            f"{path.relative_to(ROOT)} is numbered {number} but its heading says {heading.group(1)}"
        )


def test_the_development_guide_names_exactly_the_required_checks() -> None:
    checks = _table_checks(_branch_protection_section())

    assert checks == _check_names(), (
        "docs/development.md and the workflows disagree about what a merge to main waits for. "
        f"Documented only: {sorted(checks - _check_names())}. "
        f"Required but undocumented: {sorted(_check_names() - checks)}."
    )


def test_the_development_guide_names_the_label_the_merge_path_requires() -> None:
    section = _branch_protection_section()
    named = set(CODE_SPAN.findall(section)) & REQUIRED_LABELS

    assert "ai-merge-safe" in named, (
        "docs/development.md does not name `ai-merge-safe`, which is the trust label gate 1 of "
        f"scripts/pr_ai_authorize.py requires; it names {sorted(named)}"
    )


def test_the_architecture_index_names_every_required_check() -> None:
    text = ARCHITECTURE.read_text(encoding="utf-8")
    section = text.split("## Pull Request Guardrails", 1)[1].split("\n## ", 1)[0]
    named = set(CODE_SPAN.findall(section))

    missing = sorted(_check_names() - named)

    assert not missing, f"docs/architecture/README.md does not name the required checks: {missing}"
