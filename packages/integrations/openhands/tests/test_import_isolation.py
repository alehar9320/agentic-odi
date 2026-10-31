"""Import-isolation test: the orchestrator engine must not import ODI core.

Only the ports module and the ODI adapter may import ``agentic_odi_core``.
The engine (service, daemon, store, models, config, policy, signals,
github_source) must depend solely on port protocols so the orchestrator can
be tested in isolation from ODI core and any external service.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "agentic_odi_integrations_openhands"

# Engine modules that must NOT import agentic_odi_core directly.
ENGINE_MODULES = [
    "service",
    "daemon",
    "store",
    "models",
    "config",
    "policy",
    "signals",
    "github_source",
]

# Boundary modules that ARE allowed to import agentic_odi_core.
BOUNDARY_MODULES = ["ports", "adapters/odi"]


def _top_level_imports(module_path: Path) -> set[str]:
    """Return the set of top-level packages imported by a Python module."""
    tree = ast.parse(module_path.read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    return imported


def _imported_names(module_path: Path) -> set[str]:
    """Return the set of specific names imported from agentic_odi_core."""
    tree = ast.parse(module_path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("agentic_odi_core")
        ):
            for alias in node.names:
                names.add(alias.name)
    return names


# Concrete ODI core implementations that engine modules must NOT import.
# Type/enum imports (SignalKind, ScheduledWorkStatus, etc.) are allowed.
FORBIDDEN_CORE_NAMES = {"ODIService", "build_repository"}


@pytest.mark.parametrize("module_name", ENGINE_MODULES)
def test_engine_module_does_not_import_odi_core(module_name: str) -> None:
    """Engine modules must not import concrete ODI core implementations."""
    module_path = SRC / f"{module_name}.py"
    imports = _top_level_imports(module_path)
    # Top-level import of agentic_odi_core is OK only for type/enum references;
    # the concrete implementations must not be imported.
    if "agentic_odi_core" in imports:
        names = _imported_names(module_path)
        forbidden = names & FORBIDDEN_CORE_NAMES
        assert not forbidden, (
            f"{module_name} imports forbidden ODI core names: {forbidden}. "
            f"Engine modules must depend only on ports, not on ODI core implementations."
        )


@pytest.mark.parametrize("module_name", BOUNDARY_MODULES)
def test_boundary_module_may_import_odi_core(module_name: str) -> None:
    """Boundary modules (ports, adapters) are allowed to import ODI core."""
    module_path = SRC / f"{module_name}.py"
    imports = _top_level_imports(module_path)
    assert "agentic_odi_core" in imports, (
        f"{module_name} should import agentic_odi_core as the boundary adapter."
    )


def test_ports_are_protocols() -> None:
    """Ports must be Protocol subclasses (structural, not nominal)."""
    tree = ast.parse((SRC / "ports.py").read_text())
    class_names = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(isinstance(base, ast.Name) and base.id == "Protocol" for base in node.bases)
    ]
    expected = {"SignalPort", "SchedulePort", "ClockPort", "IssueTrackerPort"}
    assert set(class_names) == expected, f"Expected ports {expected}, got {set(class_names)}"
