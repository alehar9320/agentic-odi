"""The README's Code Overview table must match the actual workspace.

The table is hand-maintained, so it can quietly omit a new distribution or keep
one that was deleted. This test reads the uv workspace and the distributions'
own pyproject files, then checks the table in both directions.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def _workspace_members() -> list[str]:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = text.split("[tool.uv.workspace]", 1)[1]
    members = block.split("members = [", 1)[1].split("]", 1)[0]
    return re.findall(r'"([^"]+)"', members)


def _distribution_name(member: str) -> str:
    text = (ROOT / member / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^name = "([^"]+)"', text, re.MULTILINE)
    assert match is not None, f"{member}/pyproject.toml has no project name"
    return match.group(1)


def _table_rows() -> list[tuple[str, str]]:
    """``(path, distribution)`` for every row in the Code Overview table."""
    readme = README.read_text(encoding="utf-8")
    section = readme.split("## Code Overview", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| \*\*`([^`]+)`\*\* \| ([^|]+) \|", section, re.MULTILINE)
    return [(path, distribution.strip().strip("`")) for path, distribution in rows]


def test_every_distribution_appears_in_the_readme() -> None:
    listed = {distribution for _, distribution in _table_rows()}
    missing = sorted(
        name for name in map(_distribution_name, _workspace_members()) if name not in listed
    )

    assert not missing, f"README Code Overview is missing: {', '.join(missing)}"


def test_every_workspace_package_has_a_table_row() -> None:
    rows = {Path(path.rstrip("/")).name for path, _ in _table_rows()}

    for member in _workspace_members():
        assert Path(member).name in rows, f"README Code Overview has no row for {member}"


def test_the_table_names_no_distribution_that_does_not_exist() -> None:
    real = {_distribution_name(member) for member in _workspace_members()}
    claimed = {
        distribution for _, distribution in _table_rows() if distribution.startswith("agentic-odi")
    }

    assert claimed == real, f"README lists unknown distributions: {sorted(claimed - real)}"
