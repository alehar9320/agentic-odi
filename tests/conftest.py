"""Shared test configuration for cross-package tests."""

from __future__ import annotations

import os

os.environ.setdefault("AGENTIC_ODI_DB", ":memory:")
