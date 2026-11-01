"""Check the documentation against the code it describes (issue #97).

The rules are deliberately conservative. A code span is only treated as a
repository path when it names a known top-level directory, and a bash line is
only treated as a CLI command when it starts with a known entry point. When in
doubt this script says nothing, because a documentation check that cries wolf
gets ignored.

Run it locally with ``uv run python scripts/doc_check.py``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

KNOWN_TOP_LEVEL = {
    ".agents",
    ".github",
    "apps",
    "brand",
    "docs",
    "infra",
    "packages",
    "packaging",
    "scripts",
    "tests",
    "website",
}

ENTRY_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("odi",),
    ("agentic-odi",),
    ("agentic-odi-cli",),
    ("python", "-m", "agentic_odi_cli"),
    ("uv", "run", "odi"),
    ("uv", "run", "agentic-odi"),
    ("uv", "run", "python", "-m", "agentic_odi_cli"),
)

CODE_SPAN = re.compile(r"`([^`\n]+)`")
BASH_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)
ROUTE_SPAN = re.compile(r"^(GET|POST|PUT|PATCH|DELETE|HEAD)\s+(/api/\S+)$")
PATH_PARAM = re.compile(r"\{[^}]+\}")
ENV_VAR = re.compile(r"\bAGENTIC_ODI_[A-Z0-9_]+\b")
COMMAND_NAME = re.compile(r"^[a-z][a-z0-9-]*$")


def documentation(root: Path = ROOT) -> dict[str, str]:
    """Every living Markdown document the drift check reads.

    ``docs/superpowers/`` is deliberately excluded: designs and plans are a
    frozen record of what a change intended, including files another change
    later replaced. They are history, not current documentation.
    """
    paths = [root / "README.md", *sorted((root / "docs").rglob("*.md"))]
    docs: dict[str, str] = {}
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if relative.startswith("docs/superpowers/"):
            continue
        docs[relative] = path.read_text(encoding="utf-8")
    return docs


# --- File paths --------------------------------------------------------------


def documented_file_paths(text: str) -> list[str]:
    """Repository paths named in inline code spans, in order."""
    found: list[str] = []
    for match in CODE_SPAN.finditer(text):
        span = match.group(1).strip()
        span = span.split("#", 1)[0]
        span = re.sub(r":\d+(?:-\d+)?(?::\d+)?$", "", span)
        if not span or span.startswith(("http://", "https://", "/", "~", "-", "www.")):
            continue
        if any(char in span for char in "*{}<>| \t"):
            continue
        if "..." in span:
            continue
        if span.split("/", 1)[0] not in KNOWN_TOP_LEVEL:
            continue
        if any(
            part in {"dist", "build", "node_modules", "__pycache__"} for part in span.split("/")
        ):
            continue
        found.append(span)
    return found


def missing_file_paths(docs: dict[str, str], root: Path = ROOT) -> list[str]:
    missing: list[str] = []
    for text in docs.values():
        for span in documented_file_paths(text):
            if not (root / span).exists() and span not in missing:
                missing.append(span)
    return missing


# --- CLI commands ------------------------------------------------------------


def _command_path(line: str) -> tuple[str, ...] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if " # " in line:
        line = line.split(" # ", 1)[0]
    for separator in ("|", "&&", ";"):
        line = line.split(separator, 1)[0]
    line = line.strip()
    if line.startswith("$ "):
        line = line[2:].strip()
    tokens = line.split()
    for prefix in ENTRY_PREFIXES:
        if tuple(tokens[: len(prefix)]) != prefix:
            continue
        rest = tokens[len(prefix) :]
        path: list[str] = []
        for token in rest:
            if not COMMAND_NAME.match(token):
                break
            path.append(token)
        return tuple(path)
    return None


def documented_cli_commands(text: str) -> list[tuple[str, ...]]:
    commands: list[tuple[str, ...]] = []
    for block in BASH_BLOCK.findall(text):
        for line in block.splitlines():
            path = _command_path(line)
            if path:
                commands.append(path)
    return commands


def cli_command_tree() -> set[tuple[str, ...]]:
    from agentic_odi_cli.cli import app
    from typer.main import get_command

    tree: set[tuple[str, ...]] = set()

    def walk(command: object, prefix: tuple[str, ...]) -> None:
        children = getattr(command, "commands", None) or {}
        for name, child in children.items():
            path = (*prefix, name)
            tree.add(path)
            walk(child, path)

    walk(get_command(app), ())
    return tree


def missing_cli_commands(text: str, tree: set[tuple[str, ...]]) -> list[str]:
    groups = {path[:index] for path in tree for index in range(len(path))}
    known = tree | groups
    missing: list[str] = []
    for path in documented_cli_commands(text):
        if not path:
            continue
        resolved: tuple[str, ...] = ()
        consumed = 0
        while consumed < len(path) and (*resolved, path[consumed]) in known:
            resolved = (*resolved, path[consumed])
            consumed += 1
        unknown = consumed == 0 or (consumed < len(path) and resolved in groups)
        if unknown:
            label = "odi " + " ".join(path[: max(consumed + 1, 1)])
            if label not in missing:
                missing.append(label)
    return missing


# --- HTTP endpoints ----------------------------------------------------------


def documented_routes(text: str) -> list[tuple[str, str]]:
    routes: list[tuple[str, str]] = []
    for match in CODE_SPAN.finditer(text):
        span = match.group(1).strip().rstrip(".,;:)")
        route = ROUTE_SPAN.match(span)
        if route:
            routes.append((route.group(1), PATH_PARAM.sub("{}", route.group(2))))
            continue
        if span.startswith("/api/") and " " not in span and "*" not in span:
            routes.append(("ANY", PATH_PARAM.sub("{}", span)))
    return routes


def studio_routes() -> set[tuple[str, str]]:
    from agentic_odi_studio_api.studio.router import router

    routes: set[tuple[str, str]] = set()
    for route in router.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None)
        if not methods or not path.startswith("/api"):
            continue
        for method in methods:
            routes.add((method.upper(), PATH_PARAM.sub("{}", path)))
    return routes


def missing_routes(docs: dict[str, str], routes: set[tuple[str, str]]) -> list[str]:
    normalized = {(method, PATH_PARAM.sub("{}", path)) for method, path in routes}
    served_anywhere = {path for _, path in normalized}
    missing: list[str] = []
    for text in docs.values():
        for method, path in documented_routes(text):
            found = path in served_anywhere if method == "ANY" else (method, path) in normalized
            label = f"{method} {path}" if method != "ANY" else path
            if not found and label not in missing:
                missing.append(label)
    return missing


# --- Environment variables ---------------------------------------------------


def documented_env_vars(text: str) -> set[str]:
    return set(ENV_VAR.findall(text))


def source_text(root: Path = ROOT) -> str:
    chunks: list[str] = []
    for directory in ("apps", "packages", "scripts", "website", ".github"):
        for path in sorted((root / directory).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".rs", ".yml", ".yaml", ".ts", ".tsx"}:
                try:
                    chunks.append(path.read_text(encoding="utf-8"))
                except UnicodeDecodeError:
                    continue
    return "\n".join(chunks)


def missing_env_vars(docs: dict[str, str], sources: str) -> list[str]:
    documented: set[str] = set()
    for text in docs.values():
        documented |= documented_env_vars(text)
    return sorted(name for name in documented if name not in sources)


# --- README layout -----------------------------------------------------------


def readme_code_overview_paths(readme: str) -> list[str]:
    match = re.search(r"^## Code Overview\s*$(.*?)(?=^## |\Z)", readme, re.MULTILINE | re.DOTALL)
    if match is None:
        return []
    paths: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cell = stripped.split("|")[1].strip().strip("*").strip()
        span = CODE_SPAN.search(cell)
        value = span.group(1).strip() if span else cell
        if value and value != "Path":
            paths.append(value)
    return paths


# --- assistant-ui ledger ------------------------------------------------------

LEDGER_HEADING = "## The assistant-ui ledger"
LEDGER_PROJECTION_HEADING = "#### What the runtime gives us, and what we did not take"
LEDGER_STATUSES = {"Adopted", "Partial", "Planned", "Decision", "Rejected"}
LEDGER_CITATION = re.compile(r"#(\d+)")
LEDGER_DASH = "—"


def _section_lines(text: str, heading: str) -> list[str]:
    """Lines from a heading until the next heading of the same level or higher."""
    lines = text.splitlines()
    start = None
    level = len(heading) - len(heading.lstrip("#"))
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    if start is None:
        return []
    for index in range(start, len(lines)):
        match = re.match(r"^(#+) ", lines[index])
        if match is not None and len(match.group(1)) <= level:
            return lines[start:index]
    return lines[start:]


def _table_rows(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-{2,}:?", cell or "-") for cell in cells):
            continue
        if cells[0] in {"Capability", "Status"}:
            continue
        rows.append(cells)
    return rows


def ledger_errors(
    source: str,
    projection: str,
    root: Path = ROOT,
    delivered: set[str] | None = None,
) -> list[str]:
    """Check the assistant-ui ledger in docs/development.md and its projection.

    ``delivered`` is the set of issue/PR numbers this repository's history
    proves merged. It is only supplied by the command-line entry point, which
    reads git; on a shallow checkout the membership rule is skipped, because a
    green docs job must not depend on how deep the clone happened to be.
    """
    has_source = LEDGER_HEADING in source
    has_projection = LEDGER_PROJECTION_HEADING in projection
    if not has_source and not has_projection:
        return []
    issues: list[str] = []
    if not has_source:
        return ["ledger projection exists but the source section is missing"]
    if not has_projection:
        return ["the ledger exists but its Living Studio projection is missing"]

    rows: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    for cells in _table_rows(_section_lines(source, LEDGER_HEADING)):
        if len(cells) != 5:
            continue
        capability, status, file_cell, delivered_cell = cells[:4]
        if capability in seen:
            issues.append(f"duplicate ledger row: {capability}")
        seen.add(capability)
        if status not in LEDGER_STATUSES:
            issues.append(f"unknown ledger status {status!r} for {capability}")
            continue
        rows.append((capability, status, file_cell, delivered_cell))
        if status == "Adopted":
            citation = LEDGER_CITATION.fullmatch(delivered_cell)
            if citation is None:
                issues.append(f"adopted row without a merged citation: {capability}")
            elif delivered is not None and citation.group(1) not in delivered:
                issues.append(
                    f"adopted row cites #{citation.group(1)}, which history does not prove merged: {capability}"
                )
            if file_cell == LEDGER_DASH:
                issues.append(f"adopted row names no file: {capability}")
            else:
                path = file_cell.strip("`")
                if not (root / path).exists():
                    issues.append(f"adopted row names a file that does not exist: {path}")
        elif status == "Planned":
            citation = LEDGER_CITATION.fullmatch(delivered_cell)
            if citation is None:
                issues.append(f"planned row names no owning issue: {capability}")
            elif delivered is not None and citation.group(1) in delivered:
                issues.append(
                    f"planned row cites #{citation.group(1)}, which already merged: promote or reopen"
                )
        elif delivered_cell != LEDGER_DASH:
            issues.append(f"{status.lower()} row must not cite a delivery: {capability}")

    tallies: dict[str, int] = {}
    declared: dict[str, int] = {}
    for cells in _table_rows(_section_lines(source, LEDGER_HEADING)):
        if len(cells) == 2:
            if not cells[1].isdigit():
                issues.append(f"count table row is not a number: {cells[1]}")
                continue
            declared[cells[0]] = int(cells[1])
    for _, status, _, _ in rows:
        tallies[status] = tallies.get(status, 0) + 1
    for status in sorted(LEDGER_STATUSES):
        if declared.get(status) != tallies.get(status, 0):
            issues.append(
                f"count table says {declared.get(status)} {status}, the rows say {tallies.get(status, 0)}"
            )
    if declared.get("Total") != len(rows):
        issues.append(f"count table says {declared.get('Total')} total, the rows count {len(rows)}")

    projected = {
        (cells[0], cells[1], cells[3])
        for cells in _table_rows(_section_lines(projection, LEDGER_PROJECTION_HEADING))
        if len(cells) == 4
    }
    expected = {(r[0], r[1], r[3]) for r in rows if r[1] in {"Adopted", "Partial"}}
    for missing in sorted(expected - projected):
        issues.append(f"projection is missing a ledger row: {missing[0]}")
    for extra in sorted(projected - expected):
        issues.append(f"projection carries a row the ledger does not adopt: {extra[0]}")
    return issues


def delivered_references(subjects: list[str]) -> set[str]:
    """Issue/PR numbers that this repository's own history proves delivered."""
    refs: set[str] = set()
    for subject in subjects:
        if subject.startswith("Merge "):
            continue
        refs.update(LEDGER_CITATION.findall(subject))
    return refs


def git_subjects(root: Path = ROOT) -> list[str] | None:
    import subprocess

    try:
        result = subprocess.run(
            ["git", "log", "--format=%s", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.splitlines()


# --- The whole check ---------------------------------------------------------


def collect_issues(root: Path = ROOT, delivered: set[str] | None = None) -> list[str]:
    docs = documentation(root)
    issues: list[str] = []
    issues += [
        f"documented path does not exist: {path}" for path in missing_file_paths(docs, root=root)
    ]

    tree = cli_command_tree()
    seen: set[str] = set()
    for text in docs.values():
        for label in missing_cli_commands(text, tree):
            if label not in seen:
                seen.add(label)
                issues.append(f"documented CLI command does not exist: {label}")

    routes = studio_routes()
    issues += [f"documented route is not served: {label}" for label in missing_routes(docs, routes)]
    issues += [
        f"documented environment variable is never read: {name}"
        for name in missing_env_vars(docs, source_text(root))
    ]

    if "README.md" in docs:
        for path in readme_code_overview_paths(docs["README.md"]):
            if not (root / path).exists():
                issues.append(f"README Code Overview path does not exist: {path}")

    issues += [
        f"assistant-ui ledger: {issue}"
        for issue in ledger_errors(
            docs.get("docs/development.md", ""),
            docs.get("docs/living-studio.md", ""),
            root=root,
            delivered=delivered,
        )
    ]
    return issues


# --- Command line ------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    subjects = git_subjects()
    delivered = delivered_references(subjects) if subjects is not None else None
    issues = collect_issues(delivered=delivered)

    for issue in issues:
        print(f"documentation drift: {issue}", file=sys.stderr)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
