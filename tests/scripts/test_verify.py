from __future__ import annotations

import verify


def test_map_files_to_targets_python_only():
    targets = verify.map_files_to_targets(["apps/cli/main.py"])
    assert "apps/cli" in targets["python_packages"]
    assert targets["studio"] is False
    assert targets["unmapped"] == set()


def test_map_files_to_targets_studio():
    targets = verify.map_files_to_targets(["apps/studio/src/App.tsx"])
    assert targets["studio"] is True
    assert targets["python_packages"] == set()


def test_map_files_to_targets_mixed():
    targets = verify.map_files_to_targets(["apps/cli/main.py", "apps/studio/src/App.tsx"])
    assert "apps/cli" in targets["python_packages"]
    assert targets["studio"] is True


def test_map_files_to_targets_unmapped_raises_error_case():
    targets = verify.map_files_to_targets(["Makefile"])
    assert targets["unmapped"] == {"Makefile"}
