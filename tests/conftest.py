"""
Test configuration and shared fixtures.

Ensures the project root is on sys.path so that modules like `my_server`
can be imported reliably regardless of how pytest is invoked.
"""

from __future__ import annotations

import pathlib
import sys


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

