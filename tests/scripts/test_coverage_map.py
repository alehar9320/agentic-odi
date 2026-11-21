"""Unit tests for scripts/coverage_map.py (issue #88)."""

from __future__ import annotations

from pathlib import Path

from coverage_map import (
    DEVELOPMENT_DOC,
    ROOT,
    discover_tests,
    drift,
    render,
    source_pairs,
)


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_pairs_a_test_with_the_module_it_imports(tmp_path: Path) -> None:
    _write(tmp_path / "packages/core/src/agentic_odi_core/models.py")
    _write(tmp_path / "packages/core/src/agentic_odi_core/__init__.py")
    test = tmp_path / "packages/core/tests/test_service.py"
    _write(test, "from agentic_odi_core.models import Job\n")

    assert source_pairs(tmp_path, test) == ["packages/core/src/agentic_odi_core/models.py"]


def test_pairs_a_test_with_a_source_file_of_the_same_name(tmp_path: Path) -> None:
    _write(tmp_path / "packages/core/src/agentic_odi_core/models.py")
    test = tmp_path / "packages/core/tests/test_models.py"
    _write(test)

    assert source_pairs(tmp_path, test) == ["packages/core/src/agentic_odi_core/models.py"]


def test_pairs_a_front_end_test_with_the_component_it_imports(tmp_path: Path) -> None:
    _write(tmp_path / "apps/studio/src/ui/cards.tsx")
    test = tmp_path / "apps/studio/src/ui/cards.test.tsx"
    _write(test, 'import { Card } from "./cards";\n')

    assert source_pairs(tmp_path, test) == ["apps/studio/src/ui/cards.tsx"]


def test_reports_an_unpaired_test_instead_of_dropping_it(tmp_path: Path) -> None:
    test = tmp_path / "tests/test_mystery.py"
    _write(test)

    table = render(tmp_path)

    assert "`tests/test_mystery.py`" in table
    assert "no direct source pair" in table


def test_generation_is_deterministic(tmp_path: Path) -> None:
    _write(tmp_path / "apps/cli/src/agentic_odi_cli/jobs.py")
    _write(tmp_path / "apps/cli/tests/test_jobs.py")

    assert render(tmp_path) == render(tmp_path)


def test_the_committed_map_matches_the_repository() -> None:
    assert drift(ROOT, ROOT / DEVELOPMENT_DOC) == []


def test_the_scan_finds_tests_in_every_project() -> None:
    files = {path.relative_to(ROOT).as_posix() for path in discover_tests(ROOT)}

    assert "packages/core/tests/test_models.py" in files
    assert "apps/studio/src/ui/UiRenderer.test.tsx" in files
    assert "website/tests/test_site.py" in files
