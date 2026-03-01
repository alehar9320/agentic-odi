from __future__ import annotations

import pathlib
import sys
from typing import Any, Generator

import pytest

from my_server import jobs_db, steps_db, outcomes_db


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def reset_db() -> Generator[None, Any, None]:
    jobs_db.clear()
    steps_db.clear()
    outcomes_db.clear()
    yield
