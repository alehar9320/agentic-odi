"""Global CLI context (backend selection)."""

from __future__ import annotations

import os

_selected: str | None = None


def set_backend(name: str | None) -> None:
    global _selected
    _selected = name


def selected_backend() -> str:
    if _selected is not None:
        return _selected
    return os.environ.get("AGENTIC_ODI_BACKEND", "local")
