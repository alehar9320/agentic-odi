"""The package diagram is a contract, not an illustration.

``docs/architecture/README.md``'s Dependency Direction diagram is the picture a
maintainer reads to answer "what depends on what". Three separate things
describe that, and they drift apart quietly: the diagram, the ``[project]
dependencies`` each member declares, and the imports the source actually
contains. ``apps/studio-api`` imported ``agentic_odi_connectors`` from five
modules without declaring it, and nothing in the suite noticed — the edge worked
only because the workspace installs every member into one virtualenv.

These tests make all three agree, in both directions, so a new dependency edge
cannot exist in one of them alone.
"""

from __future__ import annotations

import ast
import functools
import importlib.util
import re
from pathlib import Path

import grimp

ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE = ROOT / "docs/architecture/README.md"
DISTRIBUTION_PREFIX = "agentic-odi-"


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


def _import_package(member: str) -> str:
    """The top-level import name, taken from the wheel target."""
    text = (ROOT / member / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'packages = \["src/([^"]+)"\]', text)
    assert match is not None, f"{member}/pyproject.toml declares no wheel package"
    return match.group(1)


def _member_by_import_package() -> dict[str, str]:
    return {_import_package(member): _distribution_name(member) for member in _workspace_members()}


@functools.cache
def _declared_edges() -> set[tuple[str, str]]:
    """``(importer, imported)`` for every workspace dependency that is declared."""
    distributions = {_distribution_name(member) for member in _workspace_members()}
    edges: set[tuple[str, str]] = set()
    for member in _workspace_members():
        text = (ROOT / member / "pyproject.toml").read_text(encoding="utf-8")
        section = text.split("[project]", 1)[1].split("\n[", 1)[0]
        assert "dependencies = [" in section, f"{member}/pyproject.toml has no dependencies"
        block = section.split("dependencies = [", 1)[1].split("]", 1)[0]
        for raw in re.findall(r'"([^"]+)"', block):
            name = re.split(r"[\[><=~!; ]", raw, maxsplit=1)[0]
            if name.startswith(DISTRIBUTION_PREFIX) and name in distributions:
                edges.add((_distribution_name(member), name))
    return edges


@functools.cache
def _dependency_diagram() -> str:
    """The mermaid block in the architecture index's Dependency Direction section."""
    section = ARCHITECTURE.read_text(encoding="utf-8").split("## Dependency Direction", 1)[1]
    fence = re.search(r"```mermaid\n(.*?)\n```", section.split("\n## ", 1)[0], re.DOTALL)
    assert fence is not None, (
        f"{ARCHITECTURE.relative_to(ROOT)} has no mermaid block under "
        "'## Dependency Direction'; the diagram is the contract and must stay machine-readable"
    )
    return fence.group(1)


@functools.cache
def _diagram_edges() -> set[tuple[str, str]]:
    """``(importer, imported)`` for every arrow drawn in the diagram."""
    edges: set[tuple[str, str]] = set()
    for line in _dependency_diagram().splitlines():
        if line.lstrip().startswith(("%%", "    %%")):
            continue
        for importer, imported in re.findall(
            r"\b([a-z][a-z0-9_]*)\s*-->\s*([a-z][a-z0-9_]*)\b", line
        ):
            edges.add((_node_to_distribution(importer), _node_to_distribution(imported)))
    return edges


def _node_to_distribution(node_id: str) -> str:
    return node_id.replace("_", "-")


@functools.cache
def _diagram_nodes() -> set[str]:
    return {
        _node_to_distribution(match.group(1))
        for match in re.finditer(r"^\s*([a-z][a-z0-9_]*)\[", _dependency_diagram(), re.MULTILINE)
    }


@functools.cache
def _observed_edges() -> set[tuple[str, str]]:
    """``(importer, imported)`` for every cross-distribution import in the source."""
    by_package = _member_by_import_package()
    for package in by_package:
        spec = importlib.util.find_spec(package)
        origin = Path(spec.origin).resolve() if spec and spec.origin else Path("")
        assert origin.is_file() and ROOT in origin.parents, (
            f"{package} resolves to {origin}, outside the repository: the workspace must be "
            "synced editable (`uv sync --all-packages`) so this analyses the checked-out source"
        )
    # No cache: the graph is small and builds in milliseconds, so a warm cache
    # would only leave a directory behind in the repo root.
    graph = grimp.build_graph(*by_package, cache_dir=None)
    edges: set[tuple[str, str]] = set()
    for module_name in graph.modules:
        importer = by_package.get(module_name.split(".")[0])
        if importer is None:
            continue
        for imported_name in graph.find_modules_directly_imported_by(module_name):
            imported = by_package.get(imported_name.split(".")[0])
            if imported is not None and imported != importer:
                edges.add((importer, imported))
    return edges


def _format(edges: set[tuple[str, str]]) -> str:
    return ", ".join(f"{importer} -> {imported}" for importer, imported in sorted(edges)) or "none"


def test_diagram_nodes_are_the_workspace_distributions() -> None:
    declared = {_distribution_name(member) for member in _workspace_members()}
    assert _diagram_nodes() == declared, (
        f"{ARCHITECTURE.relative_to(ROOT)} draws nodes for "
        f"{_format(declared - _diagram_nodes())} that are missing, or "
        f"{_format(_diagram_nodes() - declared)} that is no longer a member"
    )


def test_declared_dependencies_are_actually_imported() -> None:
    """A declared edge with no import is a dependency that can be dropped."""
    unused = _declared_edges() - _observed_edges()
    assert not unused, (
        f"declared as a workspace dependency but never imported: {_format(unused)}. "
        "Remove it, or make the diagram and the import real."
    )


def test_imports_are_all_declared_as_dependencies() -> None:
    """An imported edge with no declaration only works inside one virtualenv."""
    undeclared = _observed_edges() - _declared_edges()
    assert not undeclared, (
        f"imported without a matching [project] dependencies entry: {_format(undeclared)}. "
        "Declare it in that app's pyproject.toml, then add the same edge to "
        f"{ARCHITECTURE.relative_to(ROOT)}."
    )


def test_diagram_matches_declared_dependencies() -> None:
    diagram, declared = _diagram_edges(), _declared_edges()
    assert diagram == declared, (
        f"{ARCHITECTURE.relative_to(ROOT)} disagrees with the pyproject files. "
        f"Missing from the diagram: {_format(declared - diagram)}. "
        f"Drawn but not declared: {_format(diagram - declared)}."
    )


def test_core_is_the_leaf_of_the_workspace() -> None:
    """Documented in docs/architecture/README.md as "depends on no other package"."""
    outgoing = {edge for edge in _observed_edges() if edge[0] == "agentic-odi-core"}
    assert not outgoing, f"packages/core must import no workspace package, but: {_format(outgoing)}"


def test_no_app_imports_another_app() -> None:
    """Apps share core; they do not reach sideways into each other."""
    apps = {
        _distribution_name(member) for member in _workspace_members() if member.startswith("apps/")
    }
    crossing = {edge for edge in _observed_edges() if edge[0] in apps and edge[1] in apps}
    assert not crossing, f"one app imports another, which the layout forbids: {_format(crossing)}"


CORE = ROOT / "packages/core/src/agentic_odi_core"

# The four groups described in docs/architecture/README.md and decided in
# docs/architecture/adr/0005-core-layers-and-the-contract-split.md. Every module
# in the package belongs to exactly one of them, which
# test_every_core_module_is_in_exactly_one_group checks, so this block cannot
# fall behind the document it describes. ``__init__.py`` is excluded: it
# re-exports the whole package and would belong to all four.
CORE_LAYERS: dict[str, tuple[str, ...]] = {
    "domain": (
        "models",
        "evaluation",
        "mapping",
        "corpus",
        "transcript",
        "schedule",
        "traceability",
        "freshness",
    ),
    "persistence": (
        "repository",
        "sqlite_repository",
        "intent_store",
        "events",
        "funnel",
        "factory",
        "integrity",
        "recovery",
    ),
    "methodology": ("services", "segmentation", "strategy", "router", "messages", "steve_jobs"),
    "contract": ("contract", "errors", "remote", "schema", "connection", "consent"),
}

CORE_PACKAGE = "agentic_odi_core"


def _imported_core_modules(module_path: Path) -> set[str]:
    """Names of ``agentic_odi_core`` modules this file imports.

    Parsed rather than grepped: ``repository.py`` says ``add_strategy`` a dozen
    times and imports no methodology module at all, so a text match on the
    group's names would report a violation that is not one.
    """
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == CORE_PACKAGE and len(parts) > 1:
                    imported.add(parts[1])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # A relative import stays inside the package, but it names the
                # same modules, so it has to be read the same way.
                if node.module:
                    imported.add(node.module.split(".")[0])
                else:
                    imported.update(alias.name for alias in node.names)
                continue
            parts = (node.module or "").split(".")
            if parts[0] != CORE_PACKAGE:
                continue
            if len(parts) > 1:
                imported.add(parts[1])
            else:
                # ``from agentic_odi_core import services`` — the names are modules.
                imported.update(alias.name for alias in node.names)
    return imported


def test_persistence_imports_no_methodology() -> None:
    """Persistence stores what the other groups decide; it does not decide anything.

    The direction the layering depends on: ``services.py`` owns the ODI service
    door, and a repository that reached back into it would make storage and
    methodology one knot instead of two layers.
    """
    methodology = set(CORE_LAYERS["methodology"])
    breaches: list[tuple[str, str]] = []
    for module in CORE_LAYERS["persistence"]:
        path = CORE / f"{module}.py"
        assert path.is_file(), (
            f"{path.relative_to(ROOT)} is listed as persistence but does not exist"
        )
        for imported in methodology & _imported_core_modules(path):
            breaches.append((module, imported))
    assert not breaches, (
        "persistence imports methodology, which inverts the layering: "
        + _format({(f"persistence/{m}", f"methodology/{i}") for m, i in breaches})
        + ". Persistence may hold domain types; it may not call the service door."
    )


def test_every_core_module_is_in_exactly_one_group() -> None:
    """So a newcomer editing `packages/core` can name the group they are in.

    The four groups are a claim the docs make about the package; this is what
    keeps the claim current as modules are added and removed. It also refuses an
    invented file: issue #467 lists `signals` under methodology, and there is no
    `signals.py` — a signal is a domain type that persistence stores and
    methodology raises — so a group list copied from the issue would fail here
    rather than in review.
    """
    grouped = [module for group in CORE_LAYERS.values() for module in group]
    duplicates = sorted({module for module in grouped if grouped.count(module) > 1})
    real = {path.stem for path in CORE.glob("*.py")} - {"__init__"}
    ungrouped = sorted(real - set(grouped))
    invented = sorted(set(grouped) - real)
    assert not (duplicates or ungrouped or invented), (
        f"CORE_LAYERS must name every module in {CORE.relative_to(ROOT)} once: "
        f"in two groups: {_format_names(duplicates)}; in no group: "
        f"{_format_names(ungrouped)}; not a module: {_format_names(invented)}. "
        "Edit this list and docs/architecture/README.md together."
    )


def _format_names(names: list[str]) -> str:
    return ", ".join(names) or "none"
