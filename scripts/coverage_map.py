"""Generate the test-to-source coverage map (issue #88).

The map pairs every test file with the source files it exercises, by import
path and by name. It is committed between markers in ``docs/development.md``;
CI regenerates it and fails when the two disagree.

    uv run python scripts/coverage_map.py --write   # update the document
    uv run python scripts/coverage_map.py --check   # CI drift check
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT_DOC = "docs/development.md"
START = "<!-- coverage-map:start -->"
END = "<!-- coverage-map:end -->"

PY_SUFFIXES = (".py",)
TS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx")
TS_IMPORT = re.compile(r'from\s+"(\.[^"]+)"')
UNPAIRED = "— no direct source pair"


def _source_roots(root: Path) -> list[Path]:
    roots = sorted(root.glob("apps/*/src")) + sorted(root.glob("packages/*/src"))
    roots += [root / "scripts", root / "website/tools", root / "brand/tools"]
    return [path for path in roots if path.is_dir()]


def discover_tests(root: Path) -> list[Path]:
    found: list[Path] = []
    for area in ("apps", "packages"):
        found += sorted((root / area).glob("*/tests/**/*.py"))
    found += sorted((root / "tests").rglob("*.py"))
    found += sorted((root / "brand/tests").rglob("*.py"))
    found += sorted((root / "website/tests").rglob("*.py"))
    studio_src = root / "apps/studio/src"
    found += sorted(studio_src.rglob("*.test.ts")) + sorted(studio_src.rglob("*.test.tsx"))
    found += sorted((root / "apps/studio/e2e").rglob("*.spec.ts"))
    return [
        path
        for path in sorted(set(found))
        if path.name != "conftest.py" and "__pycache__" not in path.parts
    ]


def _source_index(root: Path) -> dict[str, list[str]]:
    """Every source stem mapped to its repository-relative files."""
    index: dict[str, list[str]] = {}
    for source_root in _source_roots(root):
        for path in source_root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", *TS_SUFFIXES}:
                continue
            if path.name == "__init__.py" or "tests" in path.parts:
                continue
            index.setdefault(path.stem, []).append(path.relative_to(root).as_posix())
    return index


def _candidate_stems(test: Path) -> list[str]:
    stem = test.name
    for suffix in (".test.tsx", ".test.ts", ".spec.ts", ".py"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if stem.startswith("test_"):
        stem = stem[len("test_") :]
    stems = {stem, stem.removesuffix("_cli")}
    if stem.startswith("studio_"):
        stems.add(stem[len("studio_") :])
    return sorted(stems)


def _python_imports(test: Path) -> set[str]:
    try:
        tree = ast.parse(test.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def _resolve_python(root: Path, module: str) -> str | None:
    parts = module.split(".")
    for source_root in _source_roots(root):
        candidate = source_root.joinpath(*parts).with_suffix(".py")
        if candidate.is_file() and candidate.name != "__init__.py":
            return candidate.relative_to(root).as_posix()
    return None


def _ts_relative(root: Path, test: Path) -> set[str]:
    found: set[str] = set()
    text = test.read_text(encoding="utf-8")
    for spec in TS_IMPORT.findall(text):
        base = (test.parent / spec).resolve()
        for suffix in ("", *TS_SUFFIXES):
            candidate = base.with_name(base.name + suffix) if suffix else base
            if candidate.is_file() and ".test." not in candidate.name:
                try:
                    found.add(candidate.relative_to(root).as_posix())
                except ValueError:
                    pass
                break
    return found


def _project_prefix(root: Path, test: Path) -> str:
    """The directory a test belongs to, used to scope name matches."""
    parts = test.relative_to(root).parts
    if parts[0] in {"apps", "packages"} and len(parts) >= 3 and parts[2] == "tests":
        return f"{parts[0]}/{parts[1]}/"
    if parts[0] in {"website", "brand"}:
        return f"{parts[0]}/"
    return ""


def source_pairs(root: Path, test: Path, index: dict[str, list[str]] | None = None) -> list[str]:
    """The repository-relative source files this test exercises.

    Python tests pair through their imports; a test with no resolvable import
    falls back to a same-name source in the same project. Front-end tests pair
    through relative imports plus a same-directory component of the same name.
    """
    index = index if index is not None else _source_index(root)
    found: set[str] = set()
    if test.suffix == ".py":
        for module in _python_imports(test):
            resolved = _resolve_python(root, module)
            if resolved is not None:
                found.add(resolved)
        if not found:
            prefix = _project_prefix(root, test)
            for stem in _candidate_stems(test):
                found.update(rel for rel in index.get(stem, []) if rel.startswith(prefix))
    else:
        found.update(_ts_relative(root, test))
        component = test.name.split(".test.")[0].split(".spec.")[0]
        for suffix in TS_SUFFIXES:
            same_dir = test.with_name(component + suffix)
            if same_dir.is_file():
                found.add(same_dir.relative_to(root).as_posix())
    try:
        found.discard(test.relative_to(root).as_posix())
    except ValueError:
        pass
    return sorted(found)


def coverage_map(root: Path) -> list[tuple[str, list[str]]]:
    index = _source_index(root)
    return [
        (test.relative_to(root).as_posix(), source_pairs(root, test, index))
        for test in discover_tests(root)
    ]


def render(root: Path) -> str:
    rows = ["| Test file | Exercises |", "|---|---|"]
    for name, sources in coverage_map(root):
        cell = "<br>".join(f"`{source}`" for source in sources) or UNPAIRED
        rows.append(f"| `{name}` | {cell} |")
    return "\n".join(rows)


def _section(document: str) -> str:
    start = document.find(START)
    end = document.find(END)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"the document has no {START} … {END} section")
    return document[start + len(START) : end].strip("\n")


def updated_document(root: Path, document: str) -> str:
    start = document.find(START)
    end = document.find(END)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"the document has no {START} … {END} section")
    return document[: start + len(START)] + "\n" + render(root) + "\n" + document[end:]


def drift(root: Path, document_path: Path) -> list[str]:
    try:
        committed = _section(document_path.read_text(encoding="utf-8"))
    except ValueError as error:
        return [str(error)]
    if committed != render(root):
        return ["the coverage map is stale; run uv run python scripts/coverage_map.py --write"]
    return []


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the committed map is stale")
    parser.add_argument("--write", action="store_true", help="rewrite the committed map")
    args = parser.parse_args(list(argv) if argv is not None else None)

    document_path = ROOT / DEVELOPMENT_DOC
    if args.write:
        document_path.write_text(
            updated_document(ROOT, document_path.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        print(f"updated {DEVELOPMENT_DOC}")
        return 0
    if args.check:
        problems = drift(ROOT, document_path)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    print(render(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
