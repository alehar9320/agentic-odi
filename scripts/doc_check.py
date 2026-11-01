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


# --- The whole check ---------------------------------------------------------


def collect_issues(root: Path = ROOT) -> list[str]:
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
    return issues


# --- Command line ------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    issues = collect_issues()

    for issue in issues:
        print(f"documentation drift: {issue}", file=sys.stderr)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
