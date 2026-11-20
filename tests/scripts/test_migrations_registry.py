"""The migration registries are contracts, and these are their guards.

The failure this catches is the one a version bump without a step produces: the
current version points past the last registered migration, and an existing
database upgrades to a version whose schema does not exist. Both stores are
checked here because the browser store solved the same problem first
(``apps/studio/src/bff/store/migrations.test.ts``) and this is the Python
equivalent.
"""

from __future__ import annotations

import re
from pathlib import Path

from agentic_odi_core import migrations as core_migrations
from agentic_odi_studio_api.studio import memory

ROOT = Path(__file__).resolve().parents[2]
INTENT_STORE = ROOT / "packages/core/src/agentic_odi_core/intent_store.py"
STUDIO_MEMORY = ROOT / "apps/studio-api/src/agentic_odi_studio_api/studio/memory.py"


def _assert_registry_is_a_gapless_ladder(registry, current_version: int, label: str) -> None:
    versions = [step.version for step in registry]
    assert versions == sorted(versions), f"{label}: migrations are out of order: {versions}"
    assert len(set(versions)) == len(versions), f"{label}: duplicate versions in {versions}"
    assert versions == list(range(1, len(versions) + 1)), (
        f"{label}: versions must be 1..N contiguous, got {versions}"
    )
    assert current_version == len(registry), (
        f"{label}: current version {current_version} does not equal the number of "
        f"registered migrations ({len(registry)}); a version was raised without a step."
    )
    for step in registry:
        assert step.description.strip(), f"{label}: migration {step.version} has no description"


def test_core_registry_is_a_gapless_ladder() -> None:
    _assert_registry_is_a_gapless_ladder(
        core_migrations.MIGRATIONS, core_migrations.CURRENT_VERSION, "odi.db"
    )


def test_studio_registry_is_a_gapless_ladder() -> None:
    registry = memory.STUDIO_MIGRATIONS
    _assert_registry_is_a_gapless_ladder(
        registry, max(step.version for step in registry), "studio.db"
    )


def test_both_stores_run_the_shared_runner() -> None:
    """The ledger is one implementation, not one per store."""
    assert "migrate(" in INTENT_STORE.read_text(encoding="utf-8")
    assert "migrate(" in STUDIO_MEMORY.read_text(encoding="utf-8")


def test_no_store_migrates_by_add_column_at_open() -> None:
    """The old per-open ``ALTER TABLE`` sweep must be gone from both stores."""
    for path in (INTENT_STORE, STUDIO_MEMORY):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\b_MIGRATIONS\b", text), (
            f"{path.name} still defines a per-open migration tuple; use the numbered registry"
        )
        assert not re.search(r"\b_migrate\(", text), (
            f"{path.name} still calls a per-open migration helper; use the numbered registry"
        )
