"""Check the documentation against the code it describes (issue #97).

The rules are deliberately conservative. A code span is only treated as a
repository path when it names a known top-level directory, and a bash line is
only treated as a CLI command when it starts with a known entry point. When in
doubt this script says nothing, because a documentation check that cries wolf
gets ignored.

Run it locally with ``uv run python scripts/doc_check.py``. In CI, pass the
pull request's changed files to also enforce the roadmap gate:

    uv run python scripts/doc_check.py --changed-files $(git diff --name-only main...HEAD)
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterable
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

CONTRACT_PATH = "packages/core/src/agentic_odi_core/contract.py"
ROUTER_PATH = "apps/studio-api/src/agentic_odi_studio_api/studio/router.py"
ROADMAP_PATH = "docs/roadmap.md"
CLI_PREFIX = "apps/cli/src/agentic_odi_cli/"

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
            part in {"dist", "build", "coverage", "node_modules", "__pycache__"}
            for part in span.split("/")
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


# --- Roadmap gate ------------------------------------------------------------

Before = Callable[[str], "str | None"]
After = Callable[[str], "str | None"]


def _class_block(text: str, name: str) -> str:
    match = re.search(rf"^class {name}\b.*?(?=^\S|\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(0) if match else ""


def _tool_names(text: str | None) -> set[str]:
    if not text:
        return set()
    return set(re.findall(r'=\s*"([a-z][a-z0-9_]+)"', _class_block(text, "ToolName")))


def _route_decorators(text: str | None) -> set[tuple[str, str]]:
    if not text:
        return set()
    found = re.findall(r'@router\.(get|post|put|patch|delete)\(\s*["\']([^"\']+)["\']', text)
    routes: set[tuple[str, str]] = set()
    for method, path in found:
        full = path if path.startswith("/api") else "/api" + path
        routes.add((method.upper(), full))
    return routes


def _cli_commands(text: str | None) -> set[str]:
    if not text:
        return set()
    names = set(re.findall(r'@[\w.]+\.command\(\s*(?:name=)?["\']([\w-]+)["\']', text))
    names |= set(re.findall(r'\.command\(\s*name=["\']([\w-]+)["\']', text))
    names |= set(re.findall(r'add_typer\([\s\S]{0,200}?name=["\']([\w-]+)["\']', text))
    return names


def detect_capabilities(changed_files: Iterable[str], before: Before, after: After) -> list[str]:
    """Public capabilities a pull request adds, named for the error message."""
    capabilities: list[str] = []
    for path in changed_files:
        if path == CONTRACT_PATH:
            for name in sorted(_tool_names(after(path)) - _tool_names(before(path))):
                capabilities.append(f"MCP tool `{name}`")
        elif path == ROUTER_PATH:
            for method, route in sorted(
                _route_decorators(after(path)) - _route_decorators(before(path))
            ):
                capabilities.append(f"Studio API route `{method} {route}`")
        elif path.startswith(CLI_PREFIX) and path.endswith(".py"):
            for name in sorted(_cli_commands(after(path)) - _cli_commands(before(path))):
                capabilities.append(f"CLI command `{name}`")
    return capabilities


def roadmap_errors(capabilities: list[str], *, roadmap_changed: bool) -> list[str]:
    if not capabilities or roadmap_changed:
        return []
    named = ", ".join(capabilities)
    return [
        f"new capability without a roadmap entry: {named}. "
        f"Add it to the Shipped or In flight section of {ROADMAP_PATH} in this pull request."
    ]


# --- Command line ------------------------------------------------------------


def _git_text(base: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{base}:{path}"], cwd=ROOT, capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else None


def _worktree_text(path: str) -> str | None:
    candidate = ROOT / path
    if not candidate.is_file():
        return None
    return candidate.read_text(encoding="utf-8")


def _changed_since(base: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"], cwd=ROOT, capture_output=True, text=True
    )
    return [line for line in result.stdout.splitlines() if line]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--changed-files",
        nargs="*",
        default=None,
        help="Repo-relative paths changed by this pull request; enables the roadmap gate.",
    )
    parser.add_argument(
        "--base",
        default=os.environ.get("GITHUB_BASE_REF") or "origin/main",
        help="Branch the pull request targets (used to read the previous version).",
    )
    args = parser.parse_args(argv)

    issues = collect_issues()
    if args.changed_files is not None:
        changed = args.changed_files or _changed_since(args.base)
        capabilities = detect_capabilities(
            changed,
            lambda path: _git_text(args.base, path),
            _worktree_text,
        )
        issues += roadmap_errors(capabilities, roadmap_changed=ROADMAP_PATH in changed)

    for issue in issues:
        print(f"documentation drift: {issue}", file=sys.stderr)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
