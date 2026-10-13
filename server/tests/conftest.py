from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest

from server import customer_outcomes_db, jobs_db, outcomes_db, steps_db


@pytest.fixture(autouse=True)
def reset_db() -> Generator[None, Any, None]:
    jobs_db.clear()
    steps_db.clear()
    outcomes_db.clear()
    customer_outcomes_db.clear()
    yield
