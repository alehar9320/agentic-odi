"""Settings drift: declared variables, documented rows, and direct reads.

Three things have to agree, and each used to drift silently:

- every ``Field(alias=...)`` in ``settings.py`` is a variable the process reads,
- every one of those variables has a row in ``docs/reference/configuration.md``,
- and nothing new reads ``os.environ`` outside ``settings.py``.

A new variable with no doc row fails here, and so does a new direct read that
bypasses the settings module. The direct-read lists are the migration backlog
(issue #1084): they may only shrink, and a stale entry fails too, because it
hides a module that was already migrated.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from agentic_odi_core import settings

ROOT = Path(__file__).resolve().parents[2]
CONFIGURATION_DOC = ROOT / "docs/reference/configuration.md"
SETTINGS_MODULE = ROOT / "packages/core/src/agentic_odi_core/settings.py"

# Direct ``os.environ`` reads that predate the settings module. Each moves to
# ``settings.py`` in its own step of #1084; until then it is a named exception
# so a *new* read cannot slip in beside it.
DIRECT_READ_ALLOWLIST = {
    "apps/cli/src/agentic_odi_cli/backend.py",
    "apps/cli/src/agentic_odi_cli/chat.py",
    "apps/cli/src/agentic_odi_cli/connectors.py",
    "apps/cli/src/agentic_odi_cli/context.py",
    "apps/cli/src/agentic_odi_cli/flags.py",
    "apps/cli/src/agentic_odi_cli/mascot.py",
    "apps/cli/src/agentic_odi_cli/paths.py",
    "apps/cli/src/agentic_odi_cli/profile.py",
    "apps/cli/src/agentic_odi_cli/update.py",
    "apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py",
    "apps/studio-api/src/agentic_odi_studio_api/app.py",
    "apps/studio-api/src/agentic_odi_studio_api/studio/memory.py",
    "apps/studio-api/src/agentic_odi_studio_api/studio/paths.py",
    "apps/studio-api/src/agentic_odi_studio_api/studio/probes.py",
    "apps/studio-api/src/agentic_odi_studio_api/studio/sharing.py",
    "packages/core/src/agentic_odi_core/events.py",
    "packages/core/src/agentic_odi_core/factory.py",
    "packages/core/src/agentic_odi_core/recovery.py",
    "packages/core/src/agentic_odi_core/services.py",
    "packages/core/src/agentic_odi_core/sqlite_repository.py",
}

_DOCUMENTED_VAR = re.compile(r"\bAGENTIC_ODI_[A-Z0-9_]+\b")
_ENVIRON_READ = re.compile(r"os\.environ|getenv\(")


def declared_variables() -> set[str]:
    """Every environment variable a settings model declares, from its alias."""
    names: set[str] = set()
    for value in vars(settings).values():
        model_fields = getattr(value, "model_fields", None)
        if not isinstance(model_fields, dict):
            continue
        for field in model_fields.values():
            alias = getattr(field, "alias", None)
            if alias:
                names.add(alias)
    return names


def documented_variables() -> set[str]:
    """Every ``AGENTIC_ODI_*`` variable named in the configuration register."""
    return set(_DOCUMENTED_VAR.findall(CONFIGURATION_DOC.read_text(encoding="utf-8")))


def _source_files() -> list[str]:
    """Every shipped Python module, excluding test trees."""
    roots = [ROOT / "packages/core/src", ROOT / "apps"]
    found: list[str] = []
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts or "tests" in path.parts:
                continue
            found.append(path.relative_to(ROOT).as_posix())
    return found


def test_every_declared_variable_has_a_documented_row() -> None:
    assert declared_variables() - documented_variables() == set()


def test_every_documented_variable_is_declared() -> None:
    assert documented_variables() - declared_variables() == set()


def test_settings_module_declares_the_mcp_variables() -> None:
    assert {"AGENTIC_ODI_MCP_TIMEOUT", "AGENTIC_ODI_MCP_KEEPALIVE"} <= declared_variables()


def test_only_the_settings_module_reads_the_environment_in_core() -> None:
    """A direct read outside ``settings.py`` must be on the migration list."""
    offenders = [
        relative
        for relative in _source_files()
        if _ENVIRON_READ.search((ROOT / relative).read_text(encoding="utf-8"))
        and relative not in DIRECT_READ_ALLOWLIST
        and relative != SETTINGS_MODULE.relative_to(ROOT).as_posix()
    ]
    assert offenders == []


def test_the_migration_list_has_no_stale_entries() -> None:
    """A migrated module left on the list would hide a regression behind it."""
    stale = [
        relative
        for relative in sorted(DIRECT_READ_ALLOWLIST)
        if not _ENVIRON_READ.search((ROOT / relative).read_text(encoding="utf-8"))
    ]
    assert stale == []


def test_the_settings_module_is_valid_python() -> None:
    ast.parse(SETTINGS_MODULE.read_text(encoding="utf-8"))
